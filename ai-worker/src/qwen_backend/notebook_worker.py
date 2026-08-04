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
from qwen_backend.worker_protocol import RecordingAnalysisClaim
from qwen_backend.worker_settings import NotebookWorkerSettings


class NotebookWorker:
    """Own lazy local-model lifecycle and delegate one claimed job to an executor."""

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
        self._executor = RecordingJobExecutor(settings, self._run_local_runtime)

    async def run_forever(self) -> None:
        """Consume the central server's recording-analysis queue until interrupted."""

        from qwen_backend.rabbit_consumer import RabbitRecordingWorker

        await RabbitRecordingWorker(self).run_forever()

    async def run_once(self) -> bool:
        """Process at most one RabbitMQ delivery for local smoke testing."""

        from qwen_backend.rabbit_consumer import RabbitRecordingWorker

        return await RabbitRecordingWorker(self).run_once()

    async def process_claim(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
    ) -> bool:
        """Run one claimed recording job and confirm one terminal central callback."""

        return await self._executor.process_claim(client, claim)

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
