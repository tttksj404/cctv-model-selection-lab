from __future__ import annotations

from datetime import UTC, datetime, timedelta

import anyio

from qwen_backend.central_client import CentralWorkerError
from qwen_backend.rabbit_worker import RabbitJobProcessor
from qwen_backend.worker_protocol import RecordingAnalysisClaim


class Delivery:
    body = (
        b'{"commandId":"command-71","eventType":"RECORDING_ANALYSIS_JOB_CREATED",'
        b'"jobId":71,"occurredAt":"2026-08-04T00:00:00Z"}'
    )
    def __init__(self) -> None:
        self.headers: dict[str, object] = {}
        self.acked = 0
        self.rejected: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)


class ClaimedClient:
    async def claim_job(self, job_id: int) -> RecordingAnalysisClaim:
        assert job_id == 71
        return RecordingAnalysisClaim(
            jobId=71,
            status="RUNNING",
            attempt=1,
            disposition="CLAIMED",
            startedAt=datetime.now(UTC),
            claimedBy="notebook-worker",
            claimExpiresAt=datetime.now(UTC) + timedelta(minutes=5),
            leaseToken="lease-71",
        )


class InvalidWorker:
    async def process_claim(self, client: object, claim: RecordingAnalysisClaim) -> bool:
        raise CentralWorkerError(
            "worker key is invalid",
            status_code=403,
            code="INVALID_WORKER_KEY",
        )


class Scheduler:
    def __init__(self) -> None:
        self.scheduled = 0

    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        self.scheduled += 1


def test_nonretryable_processing_error_is_dead_lettered() -> None:
    async def scenario() -> None:
        delivery = Delivery()
        scheduler = Scheduler()
        processor = RabbitJobProcessor(
            InvalidWorker(),  # type: ignore[arg-type]
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )

        handled = await processor.handle(delivery, ClaimedClient())  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 0
        assert delivery.rejected == [False]
        assert scheduler.scheduled == 0

    anyio.run(scenario)

