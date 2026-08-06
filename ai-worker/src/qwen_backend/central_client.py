from __future__ import annotations

import logging
import socket
import time
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import TracebackType
from typing import Final, Literal
from urllib.parse import urlsplit

import httpx2
from pydantic import Field, JsonValue, TypeAdapter, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen_backend.candidate_runtime import RuntimeCandidate
from qwen_backend.object_storage import ObjectStorageError, S3ObjectStore, S3ObjectStoreConfig
from qwen_backend.storage_transfer import (
    StorageTransferError,
    download_time_window_to_path,
    download_to_path,
    upload_file,
)
from qwen_backend.worker_protocol import (
    DEVICE_AI_SEARCH_JOBS_PATH,
    DEVICE_KEY_HEADER,
    DEVICE_KEY_PATTERN,
    DEVICE_RECORDING_ANALYSIS_JOBS_PATH,
    INTERNAL_RECORDING_ANALYSIS_JOBS_PATH,
    MAX_UPLOAD_URL_CANDIDATES,
    WORKER_CLAIM_TOKEN_HEADER,
    WORKER_KEY_HEADER,
    DeviceAiClaimRequest,
    DeviceAiCompleteRequest,
    DeviceAiFailureRequest,
    DeviceAiHeartbeatRequest,
    DeviceAiMutationResponse,
    DeviceAiSearchJob,
    DeviceCandidateEvent,
    RecordingAnalysisClaim,
    RecordingAnalysisCompletion,
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisFailure,
    RecordingAnalysisFailureRequest,
    RecordingAnalysisResult,
    RecordingAnalysisTarget,
    RecordingAnalysisUploadUrlRequest,
    RecordingAnalysisUploadUrlRequestCandidate,
    RecordingAnalysisUploadUrls,
    RecordingAnalysisWorkerHeartbeat,
    WorkerModel,
)

logger = logging.getLogger(__name__)

_SOCKET_OPTIONS: Final[tuple[tuple[int, int, int], ...]] = (
    (socket.IPPROTO_TCP, socket.TCP_NODELAY, 1),
)
_PLACEHOLDER_API_KEYS: Final[frozenset[str]] = frozenset(
    {
        "inject-from-local-secret-store",
        "change-me",
        "changeme",
        "replace-me",
    }
)
_JSON_VALUE_ADAPTER: Final[TypeAdapter[JsonValue]] = TypeAdapter(JsonValue)


class CentralClientOptions(BaseSettings):
    """Validated HTTP policy for central API calls and signed object transfers."""

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
    request.extensions["eyesonu_request_start"] = time.perf_counter()


async def _log_response(response: httpx2.Response) -> None:
    started = response.request.extensions.get("eyesonu_request_start", time.perf_counter())
    logger.info(
        "worker HTTP method=%s path=%s status=%d elapsed_ms=%d http_version=%s",
        response.request.method,
        response.request.url.path,
        response.status_code,
        round((time.perf_counter() - started) * 1_000),
        response.http_version,
    )


def create_async_client(
    *,
    base_url: str = "",
    headers: Mapping[str, str] | None = None,
    timeout: httpx2.Timeout | None = None,
    options: CentralClientOptions | None = None,
) -> httpx2.AsyncClient:
    """Create the worker's HTTP/2 client without mutating-request retries."""

    active_options = options or CentralClientOptions()
    transport = httpx2.AsyncHTTPTransport(
        http2=True,
        retries=active_options.transport_retries,
        limits=active_options.limits(),
        socket_options=_SOCKET_OPTIONS,
    )
    return httpx2.AsyncClient(
        transport=transport,
        timeout=timeout or active_options.request_timeout(),
        base_url=base_url,
        headers=dict(headers or {}),
        event_hooks={"request": [_log_request], "response": [_log_response]},
        follow_redirects=True,
    )


class CentralWorkerError(RuntimeError):
    """A central API or signed storage request could not complete safely."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code

    @property
    def is_lease_conflict(self) -> bool:
        return self.code in {"WORKER_LEASE_CONFLICT", "AI_JOB_LEASE_LOST"}


class CentralWorkerClient:
    """Typed client for both the current Worker API and legacy Device API.

    A media-server Device Key is deliberately never sent as ``X-Worker-Key``.
    ``auto`` mode recognizes the ``msk_<id>.<secret>`` shape used by the
    central server and selects ``X-Device-Key``; tests and newer deployments
    can continue to use a non-device key with the internal Worker API.
    """

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        worker_id: str,
        client: httpx2.AsyncClient | None = None,
        options: CentralClientOptions | None = None,
        auth_mode: Literal["auto", "device", "worker"] = "auto",
        storage_config: S3ObjectStoreConfig | None = None,
    ) -> None:
        normalized_url = _normalize_central_url(base_url)
        normalized_api_key = _normalize_api_key(api_key)
        normalized_worker_id = worker_id.strip()
        if not normalized_worker_id:
            raise ValueError("AI Worker worker ID is required")
        if auth_mode == "device" and not DEVICE_KEY_PATTERN.fullmatch(normalized_api_key):
            raise ValueError("device auth mode requires a valid media-server Device Key")

        active_options = options or CentralClientOptions()
        self._worker_id = normalized_worker_id
        self._api_key = normalized_api_key
        self._auth_mode = _resolve_auth_mode(normalized_api_key, auth_mode)
        self._auth_header = DEVICE_KEY_HEADER if self._auth_mode == "device" else WORKER_KEY_HEADER
        self._download_chunk_bytes = active_options.download_chunk_bytes
        self._owns_clients = client is None
        self._client = client or create_async_client(
            base_url=normalized_url,
            headers={"Accept": "application/json", self._auth_header: normalized_api_key},
            options=active_options,
        )
        self._storage_client = (
            None
            if client is not None
            else create_async_client(
                timeout=active_options.download_timeout(), options=active_options
            )
        )
        self._object_store = (
            None
            if storage_config is None
            else S3ObjectStore(storage_config, self._storage_client or self._client)
        )

    @property
    def uses_device_key(self) -> bool:
        """Whether central calls use the media-server Device Key contract."""

        return self._auth_mode == "device"

    @property
    def uses_current_device_api(self) -> bool:
        """Whether the current backend dev AI-worker contract is active."""

        return self._auth_mode == "device"

    async def __aenter__(self) -> CentralWorkerClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        if not self._owns_clients:
            return
        await self._client.aclose()
        if self._storage_client is not None:
            await self._storage_client.aclose()

    async def claim_job(self, job_id: int) -> RecordingAnalysisClaim:
        _require_positive_job_id(job_id)
        response = await self._request(
            "POST", f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/claim"
        )
        data = self._normalize_claim_data(self._data(response))
        try:
            claim = RecordingAnalysisClaim.model_validate(data)
        except ValidationError as error:
            fields = sorted(data) if isinstance(data, dict) else []
            logger.error(
                "claim response schema failed job_id=%d fields=%s errors=%s",
                job_id,
                fields,
                error.errors(include_url=False),
            )
            raise
        if claim.job_id != job_id:
            raise CentralWorkerError("central claim response returned a different job")
        return claim

    async def claim_device_job(self, model_key: str) -> DeviceAiSearchJob | None:
        """Claim one queued recording through the current Device API contract."""

        if not self.uses_current_device_api:
            raise CentralWorkerError("current Device API requires Device Key authentication")
        request = DeviceAiClaimRequest(model_key=model_key)
        response = await self._request(
            "POST",
            f"{DEVICE_AI_SEARCH_JOBS_PATH}/claim",
            payload=request,
        )
        if response.status_code == 204:
            return None
        return DeviceAiSearchJob.model_validate(self._data(response))

    async def fetch_target(
        self,
        job_id: int,
        claim_token: str | None,
    ) -> RecordingAnalysisTarget:
        _require_positive_job_id(job_id)
        response = await self._request(
            "GET",
            f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/target",
            headers=self._claim_token_headers(claim_token),
        )
        target = RecordingAnalysisTarget.model_validate(self._data(response))
        if target.job_id != job_id:
            raise CentralWorkerError("central target response returned a different job")
        return target

    async def heartbeat(
        self,
        job_id: int,
        claim_token: str,
    ) -> RecordingAnalysisWorkerHeartbeat:
        _require_positive_job_id(job_id)
        if self.uses_current_device_api:
            await self.heartbeat_device_job(job_id, claim_token)
            return RecordingAnalysisWorkerHeartbeat(
                job_id=job_id,
                status="RUNNING",
                claim_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            )
        response = await self._request(
            "POST",
            f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/heartbeat",
            headers=self._claim_token_headers(claim_token),
        )
        heartbeat = RecordingAnalysisWorkerHeartbeat.model_validate(self._data(response))
        if heartbeat.job_id != job_id:
            raise CentralWorkerError("central heartbeat response returned a different job")
        return heartbeat

    async def heartbeat_device_job(self, job_id: int, lease_token: str) -> None:
        """Refresh a lease using the current backend Device API contract."""

        _require_positive_job_id(job_id)
        await self._request(
            "POST",
            f"{DEVICE_AI_SEARCH_JOBS_PATH}/{job_id}/heartbeat",
            payload=DeviceAiHeartbeatRequest(lease_token=lease_token),
        )

    async def create_evidence_upload_urls(
        self,
        job_id: int,
        claim_token: str | None,
        candidates: Sequence[RuntimeCandidate],
    ) -> dict[str, RecordingAnalysisEvidenceUpload]:
        """Request and validate all upload URLs, in server-sized batches."""

        _require_positive_job_id(job_id)
        uploads: dict[str, RecordingAnalysisEvidenceUpload] = {}
        for batch in _candidate_batches(candidates):
            request = RecordingAnalysisUploadUrlRequest(
                candidates=tuple(
                    RecordingAnalysisUploadUrlRequestCandidate(
                        track_id=candidate.candidate_key,
                        frame_content_type="image/jpeg",
                        crop_content_type="image/jpeg",
                    )
                    for candidate in batch
                )
            )
            response = await self._request(
                "POST",
                f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/upload-urls",
                headers=self._claim_token_headers(claim_token),
                payload=request,
            )
            parsed = RecordingAnalysisUploadUrls.model_validate(self._data(response))
            expected_track_ids = {candidate.candidate_key for candidate in batch}
            received = {candidate.track_id: candidate for candidate in parsed.candidates}
            if set(received) != expected_track_ids:
                raise CentralWorkerError(
                    "central upload URL response did not match runtime candidates"
                )
            if set(uploads).intersection(received):
                raise CentralWorkerError("central upload URL response repeated a trackId")
            uploads.update(received)
        return uploads

    async def upload_image(
        self,
        url: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None:
        try:
            await upload_file(
                self._storage_client or self._client,
                url,
                source_path,
                content_type=content_type,
                max_bytes=max_bytes,
            )
        except StorageTransferError as exception:
            raise CentralWorkerError(
                str(exception),
                status_code=exception.status_code,
            ) from exception

    async def complete(
        self,
        job_id: int,
        claim_token: str | None,
        result: RecordingAnalysisResult,
    ) -> RecordingAnalysisCompletion:
        _require_positive_job_id(job_id)
        started = time.perf_counter()
        response = await self._request(
            "POST",
            f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/result",
            headers=self._claim_token_headers(claim_token),
            payload=result,
        )
        completion = RecordingAnalysisCompletion.model_validate(self._data(response))
        if completion.job_id != job_id:
            raise CentralWorkerError("central completion response returned a different job")
        logger.info(
            "central result callback accepted job_id=%d candidates=%d status=%s elapsed_ms=%d",
            job_id,
            len(result.candidates),
            completion.status,
            round((time.perf_counter() - started) * 1_000),
        )
        return completion

    async def fail(
        self,
        job_id: int,
        claim_token: str | None,
        *,
        result_id: str,
        error_code: str,
        error_message: str,
    ) -> RecordingAnalysisFailure:
        _require_positive_job_id(job_id)
        request = RecordingAnalysisFailureRequest(
            result_id=result_id,
            error_code=error_code,
            error_message=error_message,
        )
        response = await self._request(
            "POST",
            f"{INTERNAL_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/fail",
            headers=self._claim_token_headers(claim_token),
            payload=request,
        )
        failure = RecordingAnalysisFailure.model_validate(self._data(response))
        if failure.job_id != job_id:
            raise CentralWorkerError("central failure response returned a different job")
        return failure

    async def complete_device_result(
        self,
        job_id: int,
        result: DeviceCandidateEvent,
    ) -> JsonValue:
        """Submit a legacy recording candidate using ``X-Device-Key``.

        The legacy endpoint accepts the same candidate-event shape used by a
        media server and owns the job transition on successful submission.
        It intentionally does not send worker claim or lease headers.
        """

        _require_positive_job_id(job_id)
        if not self.uses_device_key:
            raise CentralWorkerError("device result requires Device Key authentication")
        response = await self._request(
            "POST",
            f"{DEVICE_RECORDING_ANALYSIS_JOBS_PATH}/{job_id}/result",
            payload=result,
        )
        return self._data(response)

    async def complete_device_job(
        self,
        job_id: int,
        request: DeviceAiCompleteRequest,
    ) -> DeviceAiMutationResponse:
        """Commit candidates through the current backend Device API contract."""

        _require_positive_job_id(job_id)
        if not self.uses_current_device_api:
            raise CentralWorkerError("current Device API requires Device Key authentication")
        started = time.perf_counter()
        response = await self._request(
            "POST",
            f"{DEVICE_AI_SEARCH_JOBS_PATH}/{job_id}/complete",
            payload=request,
        )
        mutation = DeviceAiMutationResponse.model_validate(self._data(response))
        if mutation.job_id != job_id:
            raise CentralWorkerError("central completion response returned a different job")
        logger.info(
            "central device result callback accepted job_id=%d candidates=%d "
            "status=%s elapsed_ms=%d",
            job_id,
            len(request.candidates),
            mutation.status,
            round((time.perf_counter() - started) * 1_000),
        )
        return mutation

    async def fail_device_job(
        self,
        job_id: int,
        request: DeviceAiFailureRequest,
    ) -> DeviceAiMutationResponse:
        """Report a failure through the current backend Device API contract."""

        _require_positive_job_id(job_id)
        if not self.uses_current_device_api:
            raise CentralWorkerError("current Device API requires Device Key authentication")
        response = await self._request(
            "POST",
            f"{DEVICE_AI_SEARCH_JOBS_PATH}/{job_id}/fail",
            payload=request,
        )
        mutation = DeviceAiMutationResponse.model_validate(self._data(response))
        if mutation.job_id != job_id:
            raise CentralWorkerError("central failure response returned a different job")
        return mutation

    async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path:
        try:
            return await download_to_path(
                self._storage_client or self._client,
                url,
                destination,
                max_bytes=max_bytes,
                chunk_bytes=self._download_chunk_bytes,
            )
        except StorageTransferError as exception:
            raise CentralWorkerError(
                str(exception),
                status_code=exception.status_code,
            ) from exception

    async def download_segment(
        self,
        url: str,
        destination: Path,
        *,
        start_ms: int,
        end_ms: int,
        max_bytes: int,
        ffmpeg_path: str,
        timeout_seconds: float,
    ) -> Path:
        """Materialize one claimed recording's search window from its signed URL."""

        try:
            return await download_time_window_to_path(
                url,
                destination,
                start_ms=start_ms,
                end_ms=end_ms,
                max_bytes=max_bytes,
                ffmpeg_path=ffmpeg_path,
                timeout_seconds=timeout_seconds,
            )
        except StorageTransferError as exception:
            raise CentralWorkerError(
                str(exception),
                status_code=exception.status_code,
            ) from exception

    async def download_object(self, object_key: str, destination: Path, *, max_bytes: int) -> Path:
        """Download a private recording by object key using configured MinIO/S3 access."""

        if self._object_store is None:
            raise CentralWorkerError(
                "recordingObjectKey requires S3/MinIO storage configuration"
            )
        try:
            return await self._object_store.download(
                object_key,
                destination,
                max_bytes=max_bytes,
                chunk_bytes=self._download_chunk_bytes,
            )
        except (ObjectStorageError, OSError, ValueError) as exception:
            raise CentralWorkerError("recording object download failed") from exception

    async def upload_object(
        self,
        object_key: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None:
        """Upload a legacy analysis evidence object to private S3/MinIO."""

        if self._object_store is None:
            raise CentralWorkerError(
                "legacy Device Key result requires S3/MinIO storage configuration"
            )
        try:
            await self._object_store.upload(
                object_key,
                source_path,
                content_type=content_type,
                max_bytes=max_bytes,
            )
        except (ObjectStorageError, FileNotFoundError, OSError, ValueError) as exception:
            raise CentralWorkerError("analysis evidence upload failed") from exception

    async def _request(
        self,
        method: Literal["GET", "POST"],
        path: str,
        *,
        headers: Mapping[str, str] | None = None,
        payload: WorkerModel | None = None,
    ) -> httpx2.Response:
        request_headers = {"Accept": "application/json", self._auth_header: self._api_key}
        request_headers.update(headers or {})
        try:
            response = await self._client.request(
                method,
                path,
                headers=request_headers,
                json=None if payload is None else payload.model_dump(mode="json", by_alias=True),
            )
        except httpx2.HTTPError as exception:
            raise CentralWorkerError("central worker request failed") from exception
        if response.status_code >= 400:
            raise _central_error_from_response(response)
        return response

    @staticmethod
    def _data(response: httpx2.Response) -> JsonValue:
        payload = _decode_json_value(response)
        if not isinstance(payload, dict):
            raise CentralWorkerError("central worker response must be a JSON object")
        if "data" not in payload:
            return payload
        return payload["data"]

    @staticmethod
    def _normalize_claim_data(data: JsonValue) -> JsonValue:
        """Adapt the current Controller's duplicate flag to the worker state model.

        ``RecordingAnalysisWorkerController`` returns an ``ApiResponse`` whose
        data contains ``status`` and ``duplicate``.  The Worker state machine
        also understands the older explicit ``disposition`` field, so convert
        the current response at the HTTP boundary before Pydantic validation.
        The protocol model repeats this normalization as a defensive path for
        callers that construct the model directly.
        """

        if not isinstance(data, dict):
            return data
        if "disposition" in data or "duplicate" not in data:
            return data
        if data.get("status") != "RUNNING":
            return data
        duplicate = data["duplicate"]
        if not isinstance(duplicate, bool):
            return data
        normalized = dict(data)
        normalized["disposition"] = "LEASE_HELD" if duplicate else "CLAIMED"
        return normalized

    @staticmethod
    def _claim_token_headers(claim_token: str | None) -> dict[str, str] | None:
        if claim_token is None:
            return None
        normalized_token = claim_token.strip()
        if not normalized_token:
            raise ValueError("worker claim token is required")
        return {WORKER_CLAIM_TOKEN_HEADER: normalized_token}


def _normalize_central_url(base_url: str) -> str:
    normalized_url = base_url.strip().rstrip("/")
    parsed_url = urlsplit(normalized_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise ValueError("central API URL must use http or https")
    return normalized_url


def _normalize_api_key(api_key: str) -> str:
    normalized_api_key = api_key.strip()
    if not normalized_api_key:
        raise ValueError("AI Worker API key is required")
    if normalized_api_key.lower() in _PLACEHOLDER_API_KEYS:
        raise ValueError("AI Worker API key must not be a placeholder")
    return normalized_api_key


def _resolve_auth_mode(
    api_key: str,
    auth_mode: Literal["auto", "device", "worker"],
) -> Literal["device", "worker"]:
    if auth_mode == "device":
        return "device"
    if auth_mode == "worker":
        return "worker"
    return "device" if DEVICE_KEY_PATTERN.fullmatch(api_key) else "worker"


def _require_positive_job_id(job_id: int) -> None:
    if job_id <= 0:
        raise ValueError("job_id must be positive")


def _candidate_batches(
    candidates: Sequence[RuntimeCandidate],
) -> tuple[tuple[RuntimeCandidate, ...], ...]:
    return tuple(
        tuple(candidates[start : start + MAX_UPLOAD_URL_CANDIDATES])
        for start in range(0, len(candidates), MAX_UPLOAD_URL_CANDIDATES)
    )


def _central_error_from_response(response: httpx2.Response) -> CentralWorkerError:
    message = f"central worker request returned HTTP {response.status_code}"
    code: str | None = None
    try:
        payload = _decode_json_value(response)
    except CentralWorkerError:
        return CentralWorkerError(message, status_code=response.status_code)
    if not isinstance(payload, dict):
        return CentralWorkerError(message, status_code=response.status_code)
    candidate_code = payload.get("code")
    candidate_message = payload.get("message")
    if isinstance(candidate_code, str):
        code = candidate_code
    if isinstance(candidate_message, str):
        message = candidate_message[:500]
    return CentralWorkerError(message, status_code=response.status_code, code=code)


def _decode_json_value(response: httpx2.Response) -> JsonValue:
    try:
        return _JSON_VALUE_ADAPTER.validate_python(response.json())
    except ValueError as exception:
        raise CentralWorkerError("central worker response contains invalid JSON") from exception
