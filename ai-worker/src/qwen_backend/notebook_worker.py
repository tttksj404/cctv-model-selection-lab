from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

from qwen_backend.candidate_runtime import (
    CandidateRuntimeEngine,
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    run_runtime,
)
from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.recording_job_executor import RecordingJobExecutor
from qwen_backend.solider_clip_engine import create_engine
from qwen_backend.worker_protocol import (
    DeviceAiSearchJob,
    RabbitWorkerJobEvent,
    RecordingAnalysisClaim,
)
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_status import WorkerStatusController


class NotebookWorker:
    """Own lazy local-model lifecycle and delegate one claimed job to an executor."""

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

        self._status.start()
        try:
            await RabbitRecordingWorker(self).run_forever()
        finally:
            self._status.close()

    async def run_once(self) -> bool:
        """Process at most one RabbitMQ delivery for local smoke testing."""

        from qwen_backend.rabbit_consumer import RabbitRecordingWorker

        self._status.start()
        try:
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
        if self._engine is None:
            self._engine = self._engine_factory()
        serialized = run_runtime(request.model_dump_json(by_alias=True), self._engine)
        return CandidateRuntimeResponse.model_validate_json(serialized)


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
