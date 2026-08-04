from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import anyio

from qwen_backend.notebook_worker import NotebookWorker, NotebookWorkerSettings
from qwen_backend.rabbit_worker import RabbitJobProcessor, RabbitRecordingWorker
from qwen_backend.worker_protocol import RabbitWorkerJobEvent, RecordingAnalysisClaim


class FakeDelivery:
    def __init__(self, body: bytes, events: list[str] | None = None) -> None:
        self.body = body
        self.headers: dict[str, object] = {}
        self.acked = 0
        self.rejected: list[bool] = []
        self.events = events if events is not None else []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1
        self.events.append("ack")

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)
        self.events.append(f"reject:{requeue}")


class FakeClient:
    def __init__(self, response: RecordingAnalysisClaim | Exception) -> None:
        self.response = response
        self.claims: list[int] = []

    async def claim_job(self, job_id: int) -> RecordingAnalysisClaim:
        self.claims.append(job_id)
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


class FakeWorker:
    def __init__(self, *, processed_result: bool = True, events: list[str] | None = None) -> None:
        self.settings = SimpleNamespace()
        self.processed_result = processed_result
        self.processed: list[RecordingAnalysisClaim] = []
        self.events = events if events is not None else []

    async def process_claim(self, client: FakeClient, claim: RecordingAnalysisClaim) -> bool:
        self.processed.append(claim)
        self.events.append("process")
        return self.processed_result


class FakeRetryScheduler:
    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        raise AssertionError("this test must not schedule a retry")


class EmptyCentralClient:
    def __init__(self, *args: object, **kwargs: object) -> None:
        pass

    async def __aenter__(self) -> EmptyCentralClient:
        return self

    async def __aexit__(self, *args: object) -> None:
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

    async def channel(self, **kwargs: object) -> QosChannel:
        assert kwargs == {"publisher_confirms": True, "on_return_raises": True}
        return self._channel

    async def close(self) -> None:
        self.closed = True


def _event_body() -> bytes:
    return (
        RabbitWorkerJobEvent(
            commandId="command-71",
            eventType="RECORDING_ANALYSIS_JOB_CREATED",
            jobId=71,
            occurredAt=datetime(2026, 7, 30, tzinfo=UTC),
        )
        .model_dump_json(by_alias=True)
        .encode("utf-8")
    )


def _claimed_response() -> RecordingAnalysisClaim:
    return RecordingAnalysisClaim(
        jobId=71,
        status="RUNNING",
        attempt=1,
        disposition="CLAIMED",
        startedAt=datetime(2026, 7, 30, tzinfo=UTC),
        claimedBy="recording-ai-worker",
        claimExpiresAt=datetime(2026, 7, 30, 0, 5, tzinfo=UTC),
        leaseToken="lease-71",
    )


def _processor(worker: FakeWorker) -> RabbitJobProcessor:
    return RabbitJobProcessor(
        worker,  # type: ignore[arg-type]
        retry_scheduler=FakeRetryScheduler(),
        retry_delay_seconds=5.0,
        max_retry_attempts=3,
    )


def test_rabbit_processor_acks_only_after_terminal_processing() -> None:
    async def scenario() -> None:
        events: list[str] = []
        worker = FakeWorker(events=events)
        delivery = FakeDelivery(_event_body(), events)
        client = FakeClient(_claimed_response())

        handled = await _processor(worker).handle(delivery, client)  # type: ignore[arg-type]

        assert handled is True
        assert client.claims == [71]
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert len(worker.processed) == 1
        assert events == ["process", "ack"]

    anyio.run(scenario)


def test_rabbit_processor_dead_letters_malformed_message() -> None:
    async def scenario() -> None:
        worker = FakeWorker()
        delivery = FakeDelivery(b'{"jobId":"not-a-number"}')
        client = FakeClient(_claimed_response())

        handled = await _processor(worker).handle(delivery, client)  # type: ignore[arg-type]

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
    assert channel.queue_name == "search.target.recording.queue"
    assert connection.closed is True
