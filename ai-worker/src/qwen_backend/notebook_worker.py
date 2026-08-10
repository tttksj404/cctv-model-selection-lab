from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from time import perf_counter

from anyio.to_thread import run_sync
from dotenv import find_dotenv, load_dotenv

from qwen_backend.candidate_runtime import (
    CandidateRuntimeEngine,
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    WarmableCandidateRuntimeEngine,
    run_runtime,
)
from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.multi_model_candidate_engine import create_engine
from qwen_backend.recording_job_executor import RecordingJobExecutor
from qwen_backend.worker_instance_lock import WorkerInstanceLock
from qwen_backend.worker_protocol import (
    DeviceAiSearchJob,
    RabbitWorkerJobEvent,
    RecordingAnalysisClaim,
)
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_status import WorkerStage, WorkerStatusController

logger = logging.getLogger(__name__)


class NotebookWorker:
    """Own one process-local model lifecycle and delegate jobs to an executor."""

    def __init__(
        self,
        settings: NotebookWorkerSettings,
        *,
        engine_factory: Callable[[], CandidateRuntimeEngine] = create_engine,
        show_status_window: bool = False,
    ) -> None:
        # CandidateRuntimeEngine reads QWEN_CANDIDATE_* from os.environ. Settings
        # parsing does not populate os.environ, so dotenv must precede lazy engine creation.
        load_dotenv(find_dotenv(usecwd=True), override=False)
        self.settings = settings
        self._engine_factory = engine_factory
        self._engine: CandidateRuntimeEngine | None = None
        self._engine_lock = Lock()
        self._inference_lock = Lock()
        self._engine_ready = False
        self._engine_error: Exception | None = None
        self._status = WorkerStatusController(show_window=show_status_window)
        self._executor = RecordingJobExecutor(
            settings,
            self._run_local_runtime,
            status=self._status,
        )

    @property
    def status(self) -> WorkerStatusController:
        return self._status

    async def run_forever(self) -> None:
        """Consume the central server's recording-analysis queue until interrupted."""

        from qwen_backend.rabbit_consumer import RabbitRecordingWorker

        with WorkerInstanceLock(
            self.settings.resolved_instance_lock_file(),
            enabled=self.settings.single_instance,
        ):
            self._status.start()
            try:
                await self._prepare_runtime()
                await RabbitRecordingWorker(self).run_forever()
            finally:
                self._status.close()

    async def run_once(self) -> bool:
        """Process at most one RabbitMQ delivery for local smoke testing."""

        from qwen_backend.rabbit_consumer import RabbitRecordingWorker

        with WorkerInstanceLock(
            self.settings.resolved_instance_lock_file(),
            enabled=self.settings.single_instance,
        ):
            self._status.start()
            try:
                await self._prepare_runtime()
                return await RabbitRecordingWorker(self).run_once()
            finally:
                self._status.close()

    async def process_claim(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
    ) -> bool:
        """Run one claimed recording job and confirm one terminal central callback."""

        return await self._executor.process_claim(client, claim)

    async def process_device_event(
        self,
        client: CentralWorkerClient,
        event: RabbitWorkerJobEvent,
    ) -> bool:
        """Run an enriched legacy-dev Rabbit event with the Device Key path."""

        return await self._executor.process_device_event(client, event)

    async def process_device_claim(
        self,
        client: CentralWorkerClient,
        job: DeviceAiSearchJob,
    ) -> bool:
        """Run one job claimed through the current backend Device API."""

        return await self._executor.process_device_claim(client, job)

    def _run_local_runtime(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        with self._inference_lock:
            engine = self._ensure_engine_ready()
            serialized = run_runtime(request.model_dump_json(by_alias=True), engine)
            return CandidateRuntimeResponse.model_validate_json(serialized)

    async def _prepare_runtime(self) -> None:
        self._status.update(WorkerStage.WARMING, "모델을 메모리에 준비하는 중")
        started = perf_counter()
        try:
            await run_sync(self._ensure_engine_ready)
        except Exception as error:
            self._status.update(WorkerStage.FAILED, "모델 준비 실패")
            logger.exception("AI Worker model warm-up failed before queue consumption")
            raise RuntimeError("AI Worker model warm-up failed") from error
        logger.info(
            "AI Worker model warm-up complete elapsed_ms=%.1f model_key=%s",
            (perf_counter() - started) * 1000,
            self.settings.model_key,
        )

    def _ensure_engine_ready(self) -> CandidateRuntimeEngine:
        with self._engine_lock:
            if self._engine_error is not None:
                raise RuntimeError(
                    "model warm-up failed for this worker process"
                ) from self._engine_error
            if self._engine_ready and self._engine is not None:
                return self._engine

            started = perf_counter()
            try:
                if self._engine is None:
                    self._engine = self._engine_factory()
                    logger.info(
                        "candidate runtime engine constructed model_key=%s",
                        self._engine.model_key,
                    )
                engine = self._engine
                if isinstance(engine, WarmableCandidateRuntimeEngine):
                    engine.warm_up()
            except Exception as error:
                self._engine_error = error
                logger.exception("candidate runtime engine warm-up failed; worker is not ready")
                raise

            self._engine_ready = True
            logger.info(
                "candidate runtime engine ready elapsed_ms=%.1f model_key=%s",
                (perf_counter() - started) * 1000,
                self._engine.model_key,
            )
            return self._engine


def _load_worker_env_file(env_file: Path | None) -> None:
    """Backward-compatible import seam for tests and local launch helpers."""

    from qwen_backend.worker_cli import load_worker_env_file

    load_worker_env_file(env_file)


def main() -> int:
    """Backward-compatible console entry point."""

    from qwen_backend.worker_cli import main as worker_main

    return worker_main()


if __name__ == "__main__":
    raise SystemExit(main())

