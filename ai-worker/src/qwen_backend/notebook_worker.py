from __future__ import annotations

import argparse
import logging
import socket
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit

import anyio
from anyio.to_thread import run_sync
from dotenv import find_dotenv, load_dotenv
from pydantic import AliasChoices, Field, SecretStr, ValidationError, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from qwen_backend.candidate_runtime import (
    CandidateRuntimeEngine,
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    run_runtime,
)
from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.solider_clip_engine import create_engine
from qwen_backend.worker_protocol import (
    RecordingAnalysisClaim,
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisResult,
    RecordingAnalysisTarget,
    failure_result_id,
    result_from_runtime,
)

logger = logging.getLogger(__name__)


class NotebookWorkerSettings(BaseSettings):
    """Notebook-local configuration for a RabbitMQ-driven recording worker."""

    model_config = SettingsConfigDict(
        env_prefix="EYESONU_AI_WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    central_api_url: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_CENTRAL_API_URL",
            "CENTRAL_API_BASE_URL",
        ),
    )
    api_key: SecretStr = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_API_KEY",
            "CENTRAL_API_WORKER_KEY",
        ),
    )
    worker_id: str = Field(
        default_factory=lambda: f"notebook-{socket.gethostname()}",
        min_length=1,
        max_length=100,
    )
    model_key: str = Field(default="hybrid-solider-clip-v1", min_length=1, max_length=100)
    heartbeat_interval_seconds: float = Field(default=20.0, gt=0.5, le=300.0)
    rabbitmq_url: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_URL",
            "RABBITMQ_URL",
        ),
    )
    rabbitmq_queue: str = Field(
        default="search.target.recording.queue",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_QUEUE",
            "RABBITMQ_QUEUE",
        ),
    )
    rabbitmq_prefetch_count: int = Field(default=1, ge=1, le=1)
    rabbitmq_reconnect_delay_seconds: float = Field(default=5.0, gt=0.1, le=300.0)
    cache_dir: Path = Path("artifacts/ai-worker/cache")
    output_dir: Path = Path("artifacts/ai-worker/jobs")
    max_download_bytes: int = Field(default=5 * 1024 * 1024 * 1024, gt=0, le=50 * 1024**3)
    max_evidence_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=100 * 1024 * 1024)

    @field_validator("central_api_url")
    @classmethod
    def validate_central_api_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("central API URL must use http or https")
        return normalized

    @field_validator("api_key")
    @classmethod
    def reject_placeholder_api_key(cls, value: SecretStr) -> SecretStr:
        normalized = value.get_secret_value().strip().lower()
        if normalized in {
            "inject-from-local-secret-store",
            "change-me",
            "changeme",
            "replace-me",
        }:
            raise ValueError("AI Worker API key must not be a placeholder")
        return value

    @field_validator("rabbitmq_url")
    @classmethod
    def validate_rabbitmq_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        normalized = value.get_secret_value().strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"amqp", "amqps"} or not parsed.hostname:
            raise ValueError("RabbitMQ URL must use amqp or amqps with a host")
        if normalized.lower() in {
            "inject-from-local-secret-store",
            "change-me",
            "changeme",
            "replace-me",
        }:
            raise ValueError("RabbitMQ URL must not be a placeholder")
        return SecretStr(normalized)


class LeaseLostError(RuntimeError):
    """The central server no longer accepts this worker's terminal callback."""


class NotebookWorker:
    def __init__(
        self,
        settings: NotebookWorkerSettings,
        *,
        engine_factory: Callable[[], CandidateRuntimeEngine] = create_engine,
    ) -> None:
        # CandidateRuntimeEngine reads QWEN_CANDIDATE_* from os.environ. Settings
        # parsing does not populate os.environ, so dotenv must precede lazy engine creation.
        load_dotenv(find_dotenv(usecwd=True), override=False)
        self.settings = settings
        self._engine_factory = engine_factory
        self._engine: CandidateRuntimeEngine | None = None

    async def run_forever(self) -> None:
        """Consume the central server's recording-analysis queue until interrupted."""

        from qwen_backend.rabbit_worker import RabbitRecordingWorker

        await RabbitRecordingWorker(self).run_forever()

    async def run_once(self) -> bool:
        """Process at most one RabbitMQ delivery for local smoke testing."""

        from qwen_backend.rabbit_worker import RabbitRecordingWorker

        return await RabbitRecordingWorker(self).run_once()

    async def process_claim(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
    ) -> bool:
        """Run one claimed recording job and confirm one terminal server callback."""

        if claim.duplicate:
            logger.info("central claim is already owned job_id=%d", claim.job_id)
            return True
        lease_token = claim.lease_token
        if lease_token is None:
            raise ValueError("non-duplicate central claim omitted leaseToken")
        try:
            target = await client.fetch_target(claim.job_id, lease_token)
            if target.attempt != claim.attempt:
                raise CentralWorkerError("central target attempt does not match claimed attempt")
            result = await self._process_target(client, target, lease_token)
        except LeaseLostError:
            logger.error(
                "worker lease was lost; terminal callback was not sent job_id=%d", claim.job_id
            )
            return False
        except (
            CentralWorkerError,
            FileNotFoundError,
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exception:
            if isinstance(exception, CentralWorkerError) and exception.is_lease_conflict:
                logger.warning(
                    "worker lease conflict before failure callback job_id=%d", claim.job_id
                )
                return False
            return await self._report_failure(client, claim, lease_token, exception)

        try:
            await client.complete(claim.job_id, lease_token, result)
        except CentralWorkerError as exception:
            if exception.is_lease_conflict:
                logger.warning("worker lease conflict on completion job_id=%d", claim.job_id)
            else:
                logger.exception("central completion was not confirmed job_id=%d", claim.job_id)
            return False
        logger.info(
            "AI Worker job completed job_id=%d candidates=%d",
            claim.job_id,
            len(result.candidates),
        )
        return True

    async def _report_failure(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
        lease_token: str,
        exception: CentralWorkerError
        | FileNotFoundError
        | ImportError
        | OSError
        | RuntimeError
        | ValueError,
    ) -> bool:
        logger.exception("AI Worker job failed job_id=%d", claim.job_id)
        try:
            await client.fail(
                claim.job_id,
                lease_token,
                result_id=failure_result_id(
                    worker_id=self.settings.worker_id,
                    job_id=claim.job_id,
                    attempt=claim.attempt,
                ),
                error_code=type(exception).__name__,
                error_message=" ".join(str(exception).split()) or type(exception).__name__,
            )
        except CentralWorkerError as callback_error:
            if callback_error.is_lease_conflict:
                logger.warning(
                    "worker lease conflict while reporting failure job_id=%d", claim.job_id
                )
            else:
                logger.exception("central failure was not confirmed job_id=%d", claim.job_id)
            return False
        return True

    async def _process_target(
        self,
        client: CentralWorkerClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
    ) -> RecordingAnalysisResult:
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        job_output_dir = self.settings.output_dir / f"job-{target.job_id}-attempt-{target.attempt}"
        job_output_dir.mkdir(parents=True, exist_ok=True)
        stop_heartbeat = anyio.Event()
        lease_lost = anyio.Event()
        runtime_response: CandidateRuntimeResponse | None = None
        evidence_by_track_id: dict[str, RecordingAnalysisEvidenceUpload] = {}
        started = time.perf_counter()
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                self._heartbeat_loop,
                client,
                target.job_id,
                lease_token,
                stop_heartbeat,
                lease_lost,
            )
            try:
                target, video_path = await self._download_target_recording(
                    client,
                    target,
                    lease_token,
                )
                self._raise_if_lease_lost(lease_lost, target.job_id)
                request = CandidateRuntimeRequest(
                    model_key=self.settings.model_key,
                    job_id=target.job_id,
                    case_id=target.case_id,
                    search_condition_id=target.search_condition_id,
                    recording_id=target.recording_id,
                    camera_id=target.camera_id,
                    camera_name=target.camera_name,
                    camera_address=target.camera_code,
                    video_path=video_path,
                    reference_path=None,
                    output_dir=job_output_dir,
                    prompt=target.prompt,
                    exclusion_prompt=target.exclusion_prompt,
                    similarity_threshold=None,
                    search_from_ms=target.search_from_ms,
                    search_to_ms=target.search_to_ms,
                )
                runtime_response = await run_sync(
                    self._run_local_runtime,
                    request,
                    abandon_on_cancel=False,
                )
                self._raise_if_lease_lost(lease_lost, target.job_id)
                evidence_by_track_id = await self._upload_candidate_evidence(
                    client,
                    target,
                    lease_token,
                    runtime_response,
                )
                self._raise_if_lease_lost(lease_lost, target.job_id)
            finally:
                stop_heartbeat.set()
        self._raise_if_lease_lost(lease_lost, target.job_id)
        if runtime_response is None:
            raise RuntimeError("local inference did not return a response")
        elapsed_ms = round((time.perf_counter() - started) * 1_000)
        logger.info("local inference finished job_id=%d elapsed_ms=%d", target.job_id, elapsed_ms)
        return result_from_runtime(
            runtime_response,
            target,
            worker_id=self.settings.worker_id,
            evidence_by_track_id=evidence_by_track_id,
        )

    async def _upload_candidate_evidence(
        self,
        client: CentralWorkerClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
        runtime_response: CandidateRuntimeResponse,
    ) -> dict[str, RecordingAnalysisEvidenceUpload]:
        if not runtime_response.candidates:
            return {}
        uploads = await client.create_evidence_upload_urls(
            target.job_id,
            lease_token,
            runtime_response.candidates,
        )
        expected_track_ids = {candidate.candidate_key for candidate in runtime_response.candidates}
        if set(uploads) != expected_track_ids:
            raise CentralWorkerError("central evidence response did not match runtime candidates")
        for candidate in runtime_response.candidates:
            upload = uploads[candidate.candidate_key]
            await client.upload_image(
                upload.frame.upload_url,
                candidate.frame_path,
                content_type=upload.frame.content_type,
                max_bytes=self.settings.max_evidence_upload_bytes,
            )
            await client.upload_image(
                upload.crop.upload_url,
                candidate.crop_path,
                content_type=upload.crop.content_type,
                max_bytes=self.settings.max_evidence_upload_bytes,
            )
        return uploads

    async def _download_target_recording(
        self,
        client: CentralWorkerClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
    ) -> tuple[RecordingAnalysisTarget, Path]:
        """Download once, refreshing only an expired signed URL for the same claimed target."""

        destination = self.settings.cache_dir / f"job-{target.job_id}-attempt-{target.attempt}.mp4"
        try:
            return target, await client.download(
                target.recording_download_url,
                destination,
                max_bytes=self.settings.max_download_bytes,
            )
        except CentralWorkerError as exception:
            if exception.status_code not in {401, 403}:
                raise

            refreshed_target = await client.fetch_target(target.job_id, lease_token)
            if (
                refreshed_target.job_id != target.job_id
                or refreshed_target.attempt != target.attempt
                or refreshed_target.case_id != target.case_id
                or refreshed_target.recording_id != target.recording_id
            ):
                raise CentralWorkerError(
                    "refreshed target no longer matches the claimed recording job"
                ) from exception
            return refreshed_target, await client.download(
                refreshed_target.recording_download_url,
                destination,
                max_bytes=self.settings.max_download_bytes,
            )

    async def _heartbeat_loop(
        self,
        client: CentralWorkerClient,
        job_id: int,
        lease_token: str,
        stop: anyio.Event,
        lease_lost: anyio.Event,
    ) -> None:
        while not stop.is_set():
            with anyio.move_on_after(self.settings.heartbeat_interval_seconds) as scope:
                await stop.wait()
            if not scope.cancel_called:
                return
            try:
                await client.heartbeat(job_id, lease_token)
            except CentralWorkerError:
                lease_lost.set()
                logger.exception("AI Worker heartbeat failed job_id=%d", job_id)
                return

    def _run_local_runtime(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        if self._engine is None:
            self._engine = self._engine_factory()
        serialized = run_runtime(request.model_dump_json(by_alias=True), self._engine)
        return CandidateRuntimeResponse.model_validate_json(serialized)

    @staticmethod
    def _raise_if_lease_lost(lease_lost: anyio.Event, job_id: int) -> None:
        if lease_lost.is_set():
            raise LeaseLostError(f"lease lost for job {job_id}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the notebook-hosted EyesOnU AI Worker against the central server."
    )
    parser.add_argument(
        "--once", action="store_true", help="Consume at most one RabbitMQ job and exit."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        help="Optional dotenv file to load before worker settings and model initialization.",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def _load_worker_env_file(env_file: Path | None) -> None:
    if env_file is None:
        return
    if not env_file.is_file():
        raise ValueError(f"AI Worker environment file does not exist: {env_file}")
    load_dotenv(env_file, override=False)


def main() -> int:
    args = _parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        _load_worker_env_file(args.env_file)
        settings = NotebookWorkerSettings()  # pyright: ignore[reportCallIssue]
        worker = NotebookWorker(settings)
        if args.once:
            anyio.run(worker.run_once)
        else:
            anyio.run(worker.run_forever)
    except KeyboardInterrupt:
        logger.info("AI Worker stopped by operator")
    except (OSError, ValidationError, ValueError) as exception:
        logger.error("AI Worker startup failed: %s", exception)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
