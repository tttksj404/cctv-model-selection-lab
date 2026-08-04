from __future__ import annotations

import logging
import socket
import time
from pathlib import Path
from typing import Any, Final, cast
from urllib.parse import urlsplit

import httpx2
from anyio.to_thread import run_sync
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen_backend.candidate_runtime import RuntimeCandidate
from qwen_backend.worker_protocol import (
    MAX_WORKER_ERROR_MESSAGE_LENGTH,
    WORKER_ID_HEADER,
    WORKER_JOBS_PATH,
    WORKER_KEY_HEADER,
    WorkerClaimResponse,
    WorkerCompleteRequest,
    WorkerEvidenceUpload,
    WorkerEvidenceUploadResponse,
    WorkerHeartbeatResponse,
    WorkerJobStatusResponse,
    WorkerResult,
)

logger = logging.getLogger(__name__)

_SOCKET_OPTIONS: list[tuple[int, int, int]] = [
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
]
_PLACEHOLDER_API_KEYS: Final[frozenset[str]] = frozenset(
    {
        "inject-from-local-secret-store",
        "change-me",
        "changeme",
        "replace-me",
    }
)


class CentralClientOptions(BaseSettings):
    """Validated HTTP policy shared by central API and signed downloads."""

    model_config = SettingsConfigDict(
        env_prefix="EYESONU_AI_WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    max_connections: int = Field(default=20, ge=1, le=100)
    max_keepalive_connections: int = Field(default=8, ge=0, le=100)
    keepalive_expiry_seconds: float = Field(default=30.0, gt=0.0, le=600.0)
    transport_retries: int = Field(default=0, ge=0, le=5)
    connect_timeout_seconds: float = Field(default=5.0, gt=0.0, le=120.0)
    read_timeout_seconds: float = Field(default=30.0, gt=0.0, le=600.0)
    write_timeout_seconds: float = Field(default=10.0, gt=0.0, le=600.0)
    pool_timeout_seconds: float = Field(default=10.0, gt=0.0, le=600.0)
    download_read_timeout_seconds: float = Field(default=120.0, gt=0.0, le=3_600.0)
    download_chunk_bytes: int = Field(default=1024 * 1024, ge=64 * 1024, le=16 * 1024 * 1024)

    @model_validator(mode="after")
    def validate_connection_limits(self) -> CentralClientOptions:
        if self.max_keepalive_connections > self.max_connections:
            raise ValueError("max keepalive connections cannot exceed max connections")
        return self

    def limits(self) -> httpx2.Limits:
        return httpx2.Limits(
            max_connections=self.max_connections,
            max_keepalive_connections=self.max_keepalive_connections,
            keepalive_expiry=self.keepalive_expiry_seconds,
        )

    def request_timeout(self) -> httpx2.Timeout:
        return httpx2.Timeout(
            connect=self.connect_timeout_seconds,
            read=self.read_timeout_seconds,
            write=self.write_timeout_seconds,
            pool=self.pool_timeout_seconds,
        )

    def download_timeout(self) -> httpx2.Timeout:
        return httpx2.Timeout(
            connect=self.connect_timeout_seconds,
            read=self.download_read_timeout_seconds,
            write=self.write_timeout_seconds,
            pool=self.pool_timeout_seconds,
        )


async def _log_request(request: httpx2.Request) -> None:
    request.extensions["request_start"] = time.perf_counter()


async def _log_response(response: httpx2.Response) -> None:
    started = response.request.extensions.get("request_start", time.perf_counter())
    logger.info(
        "central worker request completed method=%s path=%s status=%s "
        "elapsed_ms=%d http_version=%s",
        response.request.method,
        response.request.url.path,
        response.status_code,
        round((time.perf_counter() - started) * 1_000),
        response.http_version,
    )


def create_async_client(
    *,
    base_url: str = "",
    headers: dict[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    limits: httpx2.Limits | None = None,
    options: CentralClientOptions | None = None,
    **kwargs: Any,
) -> httpx2.AsyncClient:
    active_options = options or CentralClientOptions()
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=active_options.transport_retries,
        limits=limits or active_options.limits(),
        socket_options=_SOCKET_OPTIONS,
    )
    return httpx2.AsyncClient(
        transport=transport,
        timeout=timeout or active_options.request_timeout(),
        base_url=base_url,
        headers=headers or {},
        event_hooks={"request": [_log_request], "response": [_log_response]},
        follow_redirects=True,
        **kwargs,
    )


class CentralWorkerError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class CentralWorkerClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        worker_id: str,
        client: httpx2.AsyncClient | None = None,
        options: CentralClientOptions | None = None,
    ) -> None:
        normalized_url = base_url.rstrip("/")
        parsed_url = urlsplit(normalized_url)
        if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
            raise ValueError("central API URL must use http or https")
        normalized_api_key = api_key.strip()
        normalized_worker_id = worker_id.strip()
        if not normalized_api_key:
            raise ValueError("AI Worker API key is required")
        if normalized_api_key.lower() in _PLACEHOLDER_API_KEYS:
            raise ValueError("AI Worker API key must not be a placeholder")
        if not normalized_worker_id:
            raise ValueError("AI Worker worker ID is required")
        active_options = options or CentralClientOptions()
        self._worker_id = normalized_worker_id
        self._download_chunk_bytes = active_options.download_chunk_bytes
        self._owns_client = client is None
        self._client = client or create_async_client(
                base_url=normalized_url,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                WORKER_KEY_HEADER: normalized_api_key,
                WORKER_ID_HEADER: normalized_worker_id,
                },
                options=active_options,
            )
        self._download_client = (
            None
            if client is not None
            else create_async_client(
                timeout=active_options.download_timeout(),
                options=active_options,
            )
        )

    async def __aenter__(self) -> CentralWorkerClient:
        return self

    async def __aexit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
            if self._download_client is not None:
                await self._download_client.aclose()

    async def claim(self, model_key: str) -> WorkerClaimResponse:
        payload = {"workerId": self._worker_id, "modelKey": model_key}
        response = await self._request("POST", f"{WORKER_JOBS_PATH}/claim", json=payload)
        return WorkerClaimResponse.model_validate(self._data(response))

    async def claim_job(self, job_id: int, model_key: str) -> WorkerClaimResponse:
        if job_id <= 0:
            raise ValueError("job_id must be positive")
        payload = {"workerId": self._worker_id, "modelKey": model_key}
        response = await self._request(
            "POST",
            f"{WORKER_JOBS_PATH}/{job_id}/claim",
            json=payload,
        )
        return WorkerClaimResponse.model_validate(self._data(response))

    async def heartbeat(self, job_id: int, lease_token: str) -> WorkerHeartbeatResponse:
        payload = {"workerId": self._worker_id, "leaseToken": lease_token}
        response = await self._request(
            "POST",
            f"{WORKER_JOBS_PATH}/{job_id}/heartbeat",
            json=payload,
        )
        return WorkerHeartbeatResponse.model_validate(self._data(response))

    async def create_evidence_upload_urls(
        self,
        job_id: int,
        lease_token: str,
        candidates: tuple[RuntimeCandidate, ...],
    ) -> dict[str, WorkerEvidenceUpload]:
        payload = {
            "workerId": self._worker_id,
            "leaseToken": lease_token,
            "candidates": [
                {
                    "candidateKey": candidate.candidate_key,
                    "frameContentType": "image/jpeg",
                    "cropContentType": "image/jpeg",
                }
                for candidate in candidates
            ],
        }
        response = await self._request(
            "POST",
            f"{WORKER_JOBS_PATH}/{job_id}/evidence-upload-urls",
            json=payload,
        )
        parsed = WorkerEvidenceUploadResponse.model_validate(self._data(response))
        if parsed.job_id != job_id:
            raise CentralWorkerError("central evidence response returned a different job")
        return {upload.candidate_key: upload for upload in parsed.uploads}

    async def upload_image(
        self,
        url: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("signed upload URL must use http or https")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        content = await run_sync(source_path.read_bytes)
        if not content:
            raise CentralWorkerError("candidate evidence image is empty")
        if len(content) > max_bytes:
            raise CentralWorkerError("candidate evidence image exceeds upload limit")
        upload_client = self._download_client or self._client
        try:
            response = await upload_client.put(
                url,
                content=content,
                headers={"Content-Type": content_type},
            )
        except httpx2.HTTPError as exception:
            raise CentralWorkerError("candidate evidence upload request failed") from exception
        if response.status_code < 200 or response.status_code >= 300:
            raise CentralWorkerError(
                f"candidate evidence upload returned HTTP {response.status_code}",
                status_code=response.status_code,
            )

    async def complete(
        self,
        job_id: int,
        lease_token: str,
        result: WorkerResult,
    ) -> WorkerJobStatusResponse:
        payload = WorkerCompleteRequest(
            worker_id=self._worker_id,
            lease_token=lease_token,
            result=result,
        ).model_dump(mode="json", by_alias=True)
        response = await self._request(
            "POST",
            f"{WORKER_JOBS_PATH}/{job_id}/complete",
            json=payload,
        )
        return WorkerJobStatusResponse.model_validate(self._data(response))

    async def fail(
        self,
        job_id: int,
        lease_token: str,
        *,
        error_code: str,
        error_message: str,
        retryable: bool,
    ) -> WorkerJobStatusResponse:
        payload = {
            "workerId": self._worker_id,
            "leaseToken": lease_token,
            "errorCode": error_code,
            "errorMessage": error_message[:MAX_WORKER_ERROR_MESSAGE_LENGTH],
            "retryable": retryable,
        }
        response = await self._request(
            "POST",
            f"{WORKER_JOBS_PATH}/{job_id}/fail",
            json=payload,
        )
        return WorkerJobStatusResponse.model_validate(self._data(response))

    async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path:
        parts = urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            raise ValueError("signed storage URL must use http or https")
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = destination.with_name(f".{destination.name}.part")
        download_client = self._download_client or self._client
        try:
            async with download_client.stream("GET", url) as response:
                if response.status_code >= 400:
                    raise CentralWorkerError(
                        f"storage download failed with status {response.status_code}",
                        status_code=response.status_code,
                    )
                content_length = response.headers.get("content-length")
                if content_length is not None:
                    try:
                        declared_length = int(content_length)
                    except ValueError as exception:
                        raise CentralWorkerError(
                            "storage object has an invalid content length"
                        ) from exception
                    if declared_length < 0:
                        raise CentralWorkerError("storage object has an invalid content length")
                    if declared_length > max_bytes:
                        raise CentralWorkerError("storage object exceeds worker download limit")
                bytes_written = 0
                with temporary_path.open("wb") as stream:
                    async for chunk in response.aiter_bytes(self._download_chunk_bytes):
                        bytes_written += len(chunk)
                        if bytes_written > max_bytes:
                            raise CentralWorkerError("storage object exceeds worker download limit")
                        stream.write(chunk)
                if bytes_written == 0:
                    raise CentralWorkerError("storage object is empty")
            temporary_path.replace(destination)
        except httpx2.HTTPError as exception:
            raise CentralWorkerError("storage download request failed") from exception
        finally:
            temporary_path.unlink(missing_ok=True)
        return destination

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx2.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
        except httpx2.HTTPError as exception:
            raise CentralWorkerError("central worker request failed") from exception
        if response.status_code >= 400:
            message = f"central worker request returned HTTP {response.status_code}"
            try:
                body = cast(object, response.json())
                if isinstance(body, dict):
                    body_map = cast(dict[str, object], body)
                    candidate_message = body_map.get("message")
                    if isinstance(candidate_message, str):
                        message = candidate_message[:500]
            except (ValueError, TypeError):
                pass
            raise CentralWorkerError(message, status_code=response.status_code)
        return response

    @staticmethod
    def _data(response: httpx2.Response) -> object:
        payload = cast(object, response.json())
        if isinstance(payload, dict):
            payload_map = cast(dict[str, object], payload)
            if "data" in payload_map:
                return payload_map["data"]
            return payload_map
        return payload
