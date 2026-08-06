from __future__ import annotations

import re
import subprocess
from collections.abc import Mapping
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


_FFMPEG_AUTH_STATUS_PATTERN = re.compile(
    r"\b(?:http(?:\s+error)?|server\s+returned)\D{0,24}(401|403)\b",
    flags=re.IGNORECASE,
)


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
    headers: Mapping[str, str] | None = None,
) -> Path:
    """Stream one bounded object to an atomic destination path."""

    _validate_signed_url(url, operation="storage")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if chunk_bytes <= 0:
        raise ValueError("chunk_bytes must be positive")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(
        f".{destination.stem}.part{destination.suffix or '.mp4'}"
    )
    try:
        async with client.stream("GET", url, headers=dict(headers or {})) as response:
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


async def download_time_window_to_path(
    url: str,
    destination: Path,
    *,
    start_ms: int,
    end_ms: int,
    max_bytes: int,
    ffmpeg_path: str,
    timeout_seconds: float,
) -> Path:
    """Materialize only a requested time window from a signed media URL.

    FFmpeg performs the seek against the signed URL.  For S3/MinIO-backed MP4
    objects this lets the HTTP demuxer request the relevant byte ranges instead
    of making the worker persist the complete recording.  The output is written
    atomically and is independently bounded by ``max_bytes``.
    """

    _validate_signed_url(url, operation="storage")
    if start_ms < 0 or end_ms <= start_ms:
        raise ValueError("media time window must have a positive duration")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    if timeout_seconds <= 0:
        raise ValueError("timeout_seconds must be positive")
    if not ffmpeg_path.strip():
        raise ValueError("ffmpeg_path must not be empty")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = destination.with_name(
        f".{destination.stem}.part{destination.suffix or '.mp4'}"
    )
    start_seconds = f"{start_ms / 1_000:.3f}"
    duration_seconds = f"{(end_ms - start_ms) / 1_000:.3f}"
    command = (
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        start_seconds,
        "-i",
        url,
        "-t",
        duration_seconds,
        "-map",
        "0:v:0",
        "-an",
        "-c",
        "copy",
        "-avoid_negative_ts",
        "make_zero",
        "-fs",
        str(max_bytes),
        str(temporary_path),
    )
    try:
        completed = await run_sync(
            _run_ffmpeg,
            command,
            timeout_seconds,
        )
        if completed.returncode != 0:
            raise StorageTransferError(
                "signed recording segment extraction failed",
                status_code=_ffmpeg_auth_status(completed.stderr),
            )
        if not temporary_path.is_file() or temporary_path.stat().st_size <= 0:
            raise StorageTransferError("signed recording segment is empty")
        if temporary_path.stat().st_size > max_bytes:
            raise StorageTransferError("signed recording segment exceeds worker download limit")
        temporary_path.replace(destination)
    except FileNotFoundError as exception:
        raise StorageTransferError("ffmpeg executable was not found") from exception
    except subprocess.TimeoutExpired as exception:
        raise StorageTransferError("signed recording segment extraction timed out") from exception
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination


def _run_ffmpeg(
    command: tuple[str, ...], timeout_seconds: float
) -> subprocess.CompletedProcess[str]:
    """Run FFmpeg without a shell and without exposing its stderr to logs."""

    return subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout_seconds,
    )


def _ffmpeg_auth_status(stderr: str) -> int | None:
    """Recover only an expired/unauthorized signed-URL status from FFmpeg stderr.

    FFmpeg owns the segmented HTTP request, so a non-zero subprocess result does
    not otherwise preserve the storage response status needed to refresh a
    presigned target URL. The text itself is never propagated to logs or API
    callbacks because it can contain the signed URL.
    """

    matched = _FFMPEG_AUTH_STATUS_PATTERN.search(stderr)
    return int(matched.group(1)) if matched is not None else None


async def upload_file(
    client: httpx2.AsyncClient,
    url: str,
    source_path: Path,
    *,
    content_type: str,
    max_bytes: int,
    headers: Mapping[str, str] | None = None,
) -> None:
    """Upload one non-empty bounded evidence image to a signed PUT URL."""

    _validate_signed_url(url, operation="upload")
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    content = await run_sync(read_checked_file, source_path, max_bytes)
    try:
        request_headers = {"Content-Type": content_type}
        request_headers.update(headers or {})
        response = await client.put(url, content=content, headers=request_headers)
    except httpx2.HTTPError as exception:
        raise StorageTransferError("candidate evidence upload request failed") from exception
    if response.status_code < 200 or response.status_code >= 300:
        raise StorageTransferError(
            f"candidate evidence upload returned HTTP {response.status_code}",
            status_code=response.status_code,
        )


def read_checked_file(source_path: Path, max_bytes: int) -> bytes:
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
