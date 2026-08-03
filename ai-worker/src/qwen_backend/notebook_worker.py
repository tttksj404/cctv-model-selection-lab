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
from pydantic import Field, SecretStr, field_validator
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
    WorkerClaimResponse,
    WorkerJob,
    WorkerResult,
    worker_result_from_runtime,
)

logger = logging.getLogger(__name__)


class NotebookWorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="EYESONU_AI_WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    central_api_url: str = Field(min_length=1)
    api_key: SecretStr = Field(min_length=1)
    worker_id: str = Field(
        default_factory=lambda: f"notebook-{socket.gethostname()}",
        min_length=1,
        max_length=100,
    )
    model_key: str = Field(default="hybrid-solider-clip-v1", min_length=1, max_length=100)
    poll_interval_seconds: float = Field(default=2.0, gt=0.1, le=60.0)
    heartbeat_interval_seconds: float = Field(default=20.0, gt=0.5, le=300.0)
    cache_dir: Path = Path("artifacts/ai-worker/cache")
    output_dir: Path = Path("artifacts/ai-worker/jobs")
    max_download_bytes: int = Field(default=5 * 1024 * 1024 * 1024, gt=0, le=50 * 1024**3)
    max_reference_download_bytes: int = Field(
        default=50 * 1024 * 1024,
        gt=0,
        le=1024 * 1024 * 1024,
    )
    once: bool = False

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


class LeaseLostError(RuntimeError):
    pass


class NotebookWorker:
    def __init__(
        self,
        settings: NotebookWorkerSettings,
        *,
        engine_factory: Callable[[], CandidateRuntimeEngine] = create_engine,
    ) -> None:
        # CandidateRuntimeEngine reads QWEN_CANDIDATE_* from os.environ.
        # pydantic-settings parses .env without mutating os.environ, so load it
        # before the lazy engine factory is first called.
        load_dotenv(find_dotenv(usecwd=True), override=False)
        if settings.heartbeat_interval_seconds >= settings.poll_interval_seconds * 100:
            logger.info(
                "worker heartbeat interval is long compared with polling interval; "
                "central lease still controls validity"
            )
        self.settings = settings
        self._engine_factory = engine_factory
        self._engine: CandidateRuntimeEngine | None = None

    async def run_forever(self) -> None:
        async with CentralWorkerClient(
            base_url=self.settings.central_api_url,
            api_key=self.settings.api_key.get_secret_value(),
            worker_id=self.settings.worker_id,
        ) as client:
            while True:
                try:
                    claimed = await self._run_once(client)
                except CentralWorkerError:
                    logger.exception("central worker polling failed")
                    claimed = False
                if not claimed:
                    await anyio.sleep(self.settings.poll_interval_seconds)

    async def run_once(self) -> bool:
        async with CentralWorkerClient(
            base_url=self.settings.central_api_url,
            api_key=self.settings.api_key.get_secret_value(),
            worker_id=self.settings.worker_id,
        ) as client:
            return await self._run_once(client)

    async def _run_once(self, client: CentralWorkerClient) -> bool:
        claim = await client.claim(self.settings.model_key)
        if claim.job is None:
            return False
        if claim.lease_token is None:
            raise RuntimeError("central claim response omitted lease token")
        job = claim.job
        logger.info("claimed AI Worker job job_id=%d recording_id=%d", job.job_id, job.recording_id)
        try:
            result = await self._process_job(client, claim)
        except LeaseLostError:
            logger.error(
                "AI Worker lease was lost; result was not acknowledged job_id=%d",
                job.job_id,
            )
            return True
        except (
            CentralWorkerError,
            FileNotFoundError,
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exception:
            retryable = isinstance(exception, (CentralWorkerError, FileNotFoundError, OSError))
            logger.exception("AI Worker job failed job_id=%d retryable=%s", job.job_id, retryable)
            try:
                await client.fail(
                    job.job_id,
                    claim.lease_token,
                    error_code=type(exception).__name__,
                    error_message=" ".join(str(exception).split()) or type(exception).__name__,
                    retryable=retryable,
                )
            except CentralWorkerError:
                logger.exception("AI Worker failure could not be reported job_id=%d", job.job_id)
            return True

        await client.complete(job.job_id, claim.lease_token, result)
        logger.info(
            "AI Worker job completed job_id=%d candidates=%d",
            job.job_id,
            len(result.candidates),
        )
        return True

    async def _process_job(
        self,
        client: CentralWorkerClient,
        claim: WorkerClaimResponse,
    ) -> WorkerResult:
        job = claim.job
        lease_token = claim.lease_token
        if job is None or lease_token is None:
            raise RuntimeError("central claim response was incomplete")
        self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
        job_output_dir = self.settings.output_dir / f"job-{job.job_id}"
        job_output_dir.mkdir(parents=True, exist_ok=True)
        video_path = await client.download(
            job.video_url,
            self.settings.cache_dir / f"job-{job.job_id}.mp4",
            max_bytes=self.settings.max_download_bytes,
        )
        reference_path: Path | None = None
        if job.reference_url is not None:
            reference_path = await client.download(
                job.reference_url,
                self.settings.cache_dir / f"job-{job.job_id}-reference.jpg",
                max_bytes=self.settings.max_reference_download_bytes,
            )
        request = CandidateRuntimeRequest(
            model_key=job.model_key,
            job_id=job.job_id,
            case_id=job.case_id,
            search_condition_id=job.search_condition_id,
            recording_id=job.recording_id,
            camera_id=job.camera_id,
            camera_name=job.camera_name,
            camera_address=job.camera_address,
            video_path=video_path,
            reference_path=reference_path,
            output_dir=job_output_dir,
            prompt=job.prompt,
            exclusion_prompt=job.exclusion_prompt,
            similarity_threshold=job.similarity_threshold,
            search_from_ms=job.search_from_ms,
            search_to_ms=job.search_to_ms,
        )
        started = time.perf_counter()
        stop_heartbeat = anyio.Event()
        lease_lost = anyio.Event()
        runtime_response: CandidateRuntimeResponse | None = None
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                self._heartbeat_loop,
                client,
                job,
                lease_token,
                stop_heartbeat,
                lease_lost,
            )
            runtime_response = await run_sync(
                self._run_local_runtime,
                request,
                abandon_on_cancel=False,
            )
            stop_heartbeat.set()
            task_group.cancel_scope.cancel()
        if lease_lost.is_set():
            raise LeaseLostError(f"lease lost for job {job.job_id}")
        if runtime_response is None:
            raise RuntimeError("local inference did not return a response")
        elapsed_ms = round((time.perf_counter() - started) * 1_000)
        return worker_result_from_runtime(runtime_response, elapsed_ms)

    async def _heartbeat_loop(
        self,
        client: CentralWorkerClient,
        job: WorkerJob,
        lease_token: str,
        stop: anyio.Event,
        lease_lost: anyio.Event,
    ) -> None:
        while True:
            with anyio.move_on_after(self.settings.heartbeat_interval_seconds) as scope:
                await stop.wait()
            if not scope.cancel_called:
                return
            try:
                await client.heartbeat(job.job_id, lease_token)
            except CentralWorkerError:
                lease_lost.set()
                logger.exception("AI Worker heartbeat failed job_id=%d", job.job_id)
                return

    def _run_local_runtime(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        if self._engine is None:
            self._engine = self._engine_factory()
        serialized = run_runtime(request.model_dump_json(by_alias=True), self._engine)
        return CandidateRuntimeResponse.model_validate_json(serialized)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the notebook-hosted EyesOnU AI Worker against the central server."
    )
    parser.add_argument("--once", action="store_true", help="Claim at most one job and exit.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=("DEBUG", "INFO", "WARNING", "ERROR"),
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    settings = NotebookWorkerSettings()  # pyright: ignore[reportCallIssue]
    try:
        if args.once:
            anyio.run(NotebookWorker(settings).run_once)
        else:
            anyio.run(NotebookWorker(settings).run_forever)
    except KeyboardInterrupt:
        logger.info("AI Worker stopped by operator")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
