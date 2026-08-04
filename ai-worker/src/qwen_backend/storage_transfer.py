from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import anyio
import httpx2
from anyio.to_thread import run_sync


class StorageTransferError(Exception):
    """A bounded signed-object transfer failed before the central callback."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _validate_signed_url(url: str, *, operation: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"signed {operation} URL must use http or https")


async def download_to_path(
    client: httpx2.AsyncClient,
    url: str,
    destination: Path,
    *,
    max_bytes: int,
    chunk_bytes: int,
) -> Path:
    """Stream one bounded object to an atomic destination path."""

    _validate_signed_url(url, operation="storage")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(f".{destination.name}.part")
    try:
        async with client.stream("GET", url) as response:
            _raise_for_download_status(response)
            _validate_content_length(response, max_bytes=max_bytes)
            bytes_written = 0
            async with await anyio.open_file(temporary_path, "wb") as stream:
                async for chunk in response.aiter_bytes(chunk_bytes):
                    bytes_written += len(chunk)
                    if bytes_written > max_bytes:
                        raise StorageTransferError("storage object exceeds worker download limit")
                    await stream.write(chunk)
            if bytes_written == 0:
                raise StorageTransferError("storage object is empty")
        temporary_path.replace(destination)
    except httpx2.HTTPError as exception:
        raise StorageTransferError("storage download request failed") from exception
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


async def upload_file(
    client: httpx2.AsyncClient,
    url: str,
    source_path: Path,
    *,
    content_type: str,
    max_bytes: int,
) -> None:
    """Upload one non-empty bounded evidence image to a signed PUT URL."""

    _validate_signed_url(url, operation="upload")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    content = await run_sync(_read_checked_file, source_path, max_bytes)
    try:
        response = await client.put(url, content=content, headers={"Content-Type": content_type})
    except httpx2.HTTPError as exception:
        raise StorageTransferError("candidate evidence upload request failed") from exception
    if response.status_code < 200 or response.status_code >= 300:
        raise StorageTransferError(
            f"candidate evidence upload returned HTTP {response.status_code}",
            status_code=response.status_code,
        )


def _read_checked_file(source_path: Path, max_bytes: int) -> bytes:
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    source_size = source_path.stat().st_size
    if source_size <= 0:
        raise StorageTransferError("candidate evidence image is empty")
    if source_size > max_bytes:
        raise StorageTransferError("candidate evidence image exceeds upload limit")
    content = source_path.read_bytes()
    if len(content) != source_size:
        raise StorageTransferError("candidate evidence image changed during upload")
    return content


def _raise_for_download_status(response: httpx2.Response) -> None:
    if response.status_code >= 400:
        raise StorageTransferError(
            f"storage download failed with status {response.status_code}",
            status_code=response.status_code,
        )


def _validate_content_length(response: httpx2.Response, *, max_bytes: int) -> None:
    content_length = response.headers.get("content-length")
    if content_length is None:
        return
    try:
        declared_length = int(content_length)
    except ValueError as exception:
        raise StorageTransferError("storage object has an invalid content length") from exception
    if declared_length < 0:
        raise StorageTransferError("storage object has an invalid content length")
    if declared_length > max_bytes:
        raise StorageTransferError("storage object exceeds worker download limit")
