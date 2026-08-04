from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import anyio

from qwen_backend.central_client import CentralWorkerError
from qwen_backend.notebook_worker import NotebookWorker, NotebookWorkerSettings
from qwen_backend.rabbit_worker import RabbitJobProcessor, RabbitRecordingWorker
from qwen_backend.worker_protocol import RabbitWorkerJobEvent, WorkerClaimResponse, WorkerJob


class FakeDelivery:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.acked = 0
        self.rejected: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)


class FakeClient:
    def __init__(self, response: WorkerClaimResponse | Exception) -> None:
        self.response = response
        self.claims: list[tuple[int, str]] = []

    async def claim_job(self, job_id: int, model_key: str) -> WorkerClaimResponse:
        self.claims.append((job_id, model_key))
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeWorker:
    def __init__(self) -> None:
        self.settings = SimpleNamespace(model_key="fixture-hybrid-v1")
        self.processed: list[WorkerClaimResponse] = []

    async def process_claim(self, client: FakeClient, claim: WorkerClaimResponse) -> bool:
        self.processed.append(claim)
        return True


class EmptyCentralClient:
    def __init__(self, *args, **kwargs) -> None:
        pass

    async def __aenter__(self) -> EmptyCentralClient:
        return self

    async def __aexit__(self, *args) -> None:
        return None


class EmptyQueue:
    async def get(self, *, fail: bool):
        assert fail is False
        return None


class QosChannel:
    def __init__(self) -> None:
        self.prefetch_count: int | None = None
        self.queue_name: str | None = None

    async def set_qos(self, *, prefetch_count: int) -> None:
        self.prefetch_count = prefetch_count

    async def declare_queue(self, name: str, *, durable: bool, passive: bool) -> EmptyQueue:
        self.queue_name = name
        assert durable is True
        assert passive is True
        return EmptyQueue()


class QosConnection:
    def __init__(self, channel: QosChannel) -> None:
        self._channel = channel
        self.closed = False

    async def channel(self) -> QosChannel:
        return self._channel

    async def close(self) -> None:
        self.closed = True


def _event_body() -> bytes:
    return RabbitWorkerJobEvent(
        eventId="command-71",
        jobId=71,
        caseId=11,
        attempt=1,
        occurredAt=datetime(2026, 7, 30, tzinfo=UTC),
    ).model_dump_json(by_alias=True).encode("utf-8")


def _claimed_response() -> WorkerClaimResponse:
    job = WorkerJob(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        modelKey="fixture-hybrid-v1",
        cameraId=41,
        cameraName="Gate A",
        cameraAddress="CAM-001",
        videoUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        similarityThreshold=0.8,
        searchFromMs=0,
        searchToMs=5_000,
        leaseExpiresAt=datetime(2026, 7, 30, 0, 1, tzinfo=UTC),
    )
    return WorkerClaimResponse(
        job=job,
        leaseToken="lease-71",
        leaseExpiresAt=job.lease_expires_at,
    )


def test_rabbit_processor_claims_exact_job_then_acks_and_processes() -> None:
    async def scenario() -> None:
        worker = FakeWorker()
        delivery = FakeDelivery(_event_body())
        client = FakeClient(_claimed_response())

        handled = await RabbitJobProcessor(worker).handle(delivery, client)  # type: ignore[arg-type]

        assert handled is True
        assert client.claims == [(71, "fixture-hybrid-v1")]
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert len(worker.processed) == 1

    anyio.run(scenario)


def test_rabbit_processor_requeues_when_central_claim_is_unavailable() -> None:
    async def scenario() -> None:
        worker = FakeWorker()
        delivery = FakeDelivery(_event_body())
        client = FakeClient(CentralWorkerError("central unavailable"))

        handled = await RabbitJobProcessor(worker).handle(delivery, client)  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 0
        assert delivery.rejected == [True]
        assert worker.processed == []

    anyio.run(scenario)


def test_rabbit_processor_dead_letters_malformed_message() -> None:
    async def scenario() -> None:
        worker = FakeWorker()
        delivery = FakeDelivery(b'{"jobId":"not-a-number"}')
        client = FakeClient(WorkerClaimResponse())

        handled = await RabbitJobProcessor(worker).handle(delivery, client)  # type: ignore[arg-type]

        assert handled is False
        assert client.claims == []
        assert delivery.acked == 0
        assert delivery.rejected == [False]

    anyio.run(scenario)


def test_rabbit_worker_configures_single_delivery_prefetch(monkeypatch) -> None:
    channel = QosChannel()
    connection = QosConnection(channel)

    async def connect_robust(url: str) -> QosConnection:
        assert url == "amqp://guest:guest@localhost/"
        return connection

    monkeypatch.setattr("qwen_backend.rabbit_worker.CentralWorkerClient", EmptyCentralClient)
    monkeypatch.setattr("qwen_backend.rabbit_worker.aio_pika.connect_robust", connect_robust)
    worker = NotebookWorker(
        NotebookWorkerSettings(
            central_api_url="https://central.example",
            api_key="test-key",
            worker_id="notebook-test",
            rabbitmq_url="amqp://guest:guest@localhost/",
        )
    )

    assert anyio.run(RabbitRecordingWorker(worker).run_once) is False
    assert channel.prefetch_count == 1
    assert channel.queue_name == "ai.worker.recording-analysis.v1"
    assert connection.closed is True
