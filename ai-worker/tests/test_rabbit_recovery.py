from __future__ import annotations

from datetime import UTC, datetime, timedelta

import aio_pika
import anyio
import pytest

from qwen_backend.central_client import CentralWorkerError
from qwen_backend.rabbit_retry import AioPikaRetryScheduler
from qwen_backend.rabbit_worker import RabbitJobProcessor, RabbitRetryUnavailable
from qwen_backend.worker_protocol import RecordingAnalysisClaim


class FakeDelivery:
    def __init__(self, body: bytes, *, headers: dict[str, int] | None = None) -> None:
        self.body = body
        self.headers = headers or {}
        self.acked = 0
        self.rejected: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)


class FakeClient:
    def __init__(self, response: RecordingAnalysisClaim | CentralWorkerError) -> None:
        self._response = response

    async def claim_job(self, job_id: int) -> RecordingAnalysisClaim:
        assert job_id == 71
        if isinstance(self._response, CentralWorkerError):
            raise self._response
        return self._response


class SequentialClient:
    def __init__(self, responses: list[RecordingAnalysisClaim]) -> None:
        self._responses = responses

    async def claim_job(self, job_id: int) -> RecordingAnalysisClaim:
        assert job_id == 71
        return self._responses.pop(0)


class FakeWorker:
    def __init__(self) -> None:
        self.processed: list[RecordingAnalysisClaim] = []

    async def process_claim(self, client: object, claim: RecordingAnalysisClaim) -> bool:
        self.processed.append(claim)
        return True


class FakeRetryScheduler:
    def __init__(self) -> None:
        self.scheduled: list[tuple[bytes, int, float]] = []

    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        self.scheduled.append((body, retry_count, delay_seconds))


class RetryPublishDenied:
    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        raise aio_pika.exceptions.AMQPException()


class ClosedDelivery(FakeDelivery):
    async def reject(self, requeue: bool = False) -> None:
        raise aio_pika.exceptions.ChannelInvalidStateError()


class CapturingExchange:
    def __init__(self) -> None:
        self.published: list[tuple[object, str]] = []

    async def publish(self, message: object, routing_key: str, *, mandatory: bool) -> None:
        assert mandatory is True
        self.published.append((message, routing_key))


class CapturingChannel:
    def __init__(self) -> None:
        self.exchange = CapturingExchange()

    async def get_exchange(self, name: str, *, ensure: bool) -> CapturingExchange:
        assert name == "search.target.recording.retry.exchange"
        assert ensure is False
        return self.exchange


def _legacy_event_body() -> bytes:
    return (
        b'{"commandId":"command-71","eventType":"RECORDING_ANALYSIS_JOB_CREATED",'
        b'"jobId":71,"caseId":11,"recordingId":31,"cameraId":41,'
        b'"cameraCode":"CAM-001","cameraName":"Gate A",'
        b'"recordingObjectKey":"recordings/CAM-001/video.mp4","attempt":1,'
        b'"occurredAt":"2026-08-04T00:00:00Z"}'
    )


def _lease_held_claim() -> RecordingAnalysisClaim:
    return RecordingAnalysisClaim(
        jobId=71,
        status="RUNNING",
        attempt=1,
        disposition="LEASE_HELD_BY_OTHER",
        startedAt=datetime.now(UTC),
        claimedBy="other-worker",
        claimExpiresAt=datetime.now(UTC) + timedelta(seconds=45),
    )


def _claimed_response() -> RecordingAnalysisClaim:
    return RecordingAnalysisClaim(
        jobId=71,
        status="RUNNING",
        attempt=1,
        disposition="CLAIMED",
        startedAt=datetime.now(UTC),
        claimedBy="recovery-worker",
        claimExpiresAt=datetime.now(UTC) + timedelta(minutes=5),
        leaseToken="lease-71",
    )


def _retry_pending_claim() -> RecordingAnalysisClaim:
    return RecordingAnalysisClaim(
        jobId=71,
        status="QUEUED",
        attempt=1,
        disposition="RETRY_PENDING",
    )


def test_retry_scheduler_routes_to_fixed_ttl_bucket() -> None:
    async def scenario() -> None:
        channel = CapturingChannel()
        scheduler = AioPikaRetryScheduler(
            channel,  # type: ignore[arg-type]
            exchange_name="search.target.recording.retry.exchange",
            routing_key_prefix="search.target.recording.retry",
        )

        await scheduler.schedule(b"{}", retry_count=0, delay_seconds=45.0)

        message, routing_key = channel.exchange.published[0]
        assert routing_key == "search.target.recording.retry.60s"
        assert message.expiration is None  # type: ignore[attr-defined]
        assert message.headers == {"x-eyesonu-retry-count": 0}  # type: ignore[attr-defined]

    anyio.run(scenario)


def test_active_foreign_lease_is_delayed_until_it_can_be_reclaimed() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body())
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )

        handled = await processor.handle(delivery, FakeClient(_lease_held_claim()))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert len(scheduler.scheduled) == 1
        assert scheduler.scheduled[0][1] == 0
        assert scheduler.scheduled[0][2] >= 40.0

    anyio.run(scenario)


def test_retry_publish_failure_on_closed_channel_is_recoverable(monkeypatch) -> None:
    async def scenario() -> None:
        sleep_calls: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr("qwen_backend.rabbit_worker.anyio.sleep", fake_sleep)
        delivery = ClosedDelivery(_legacy_event_body())
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=RetryPublishDenied(),
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )

        with pytest.raises(RabbitRetryUnavailable):
            await processor.handle(delivery, FakeClient(_lease_held_claim()))  # type: ignore[arg-type]
        assert sleep_calls and sleep_calls[0] >= 40.0

    anyio.run(scenario)


def test_retry_publish_failure_delays_source_requeue_to_avoid_a_tight_loop(monkeypatch) -> None:
    async def scenario() -> None:
        sleep_calls: list[float] = []

        async def fake_sleep(delay: float) -> None:
            sleep_calls.append(delay)

        monkeypatch.setattr("qwen_backend.rabbit_worker.anyio.sleep", fake_sleep)
        delivery = FakeDelivery(_legacy_event_body())
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=RetryPublishDenied(),
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )

        handled = await processor.handle(delivery, FakeClient(_lease_held_claim()))  # type: ignore[arg-type]

        assert handled is False
        assert sleep_calls and sleep_calls[0] >= 40.0
        assert delivery.rejected == [True]

    anyio.run(scenario)


def test_active_same_worker_lease_is_also_delayed_without_reprocessing() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body())
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )
        claim = RecordingAnalysisClaim(
            jobId=71,
            status="RUNNING",
            attempt=1,
            disposition="LEASE_HELD_BY_SELF",
            startedAt=datetime.now(UTC),
            claimedBy="notebook-worker",
            claimExpiresAt=datetime.now(UTC) + timedelta(seconds=45),
        )

        handled = await processor.handle(delivery, FakeClient(claim))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert scheduler.scheduled[0][1] == 0
        assert scheduler.scheduled[0][2] >= 40.0

    anyio.run(scenario)


def test_active_lease_does_not_consume_the_transient_retry_budget() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body(), headers={"x-eyesonu-retry-count": 20})
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=20,
        )

        handled = await processor.handle(delivery, FakeClient(_lease_held_claim()))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert scheduler.scheduled[0][1] == 20

    anyio.run(scenario)


def test_retry_pending_does_not_consume_the_transient_retry_budget() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body(), headers={"x-eyesonu-retry-count": 20})
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=20,
        )

        handled = await processor.handle(delivery, FakeClient(_retry_pending_claim()))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert scheduler.scheduled[0][1] == 20

    anyio.run(scenario)


def test_delayed_delivery_can_be_claimed_after_the_previous_lease_expires() -> None:
    async def scenario() -> None:
        scheduler = FakeRetryScheduler()
        worker = FakeWorker()
        processor = RabbitJobProcessor(
            worker,  # type: ignore[arg-type]
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )
        client = SequentialClient([_lease_held_claim(), _claimed_response()])
        first_delivery = FakeDelivery(_legacy_event_body())

        first_handled = await processor.handle(first_delivery, client)  # type: ignore[arg-type]
        delayed_delivery = FakeDelivery(_legacy_event_body(), headers={"x-eyesonu-retry-count": 0})
        second_handled = await processor.handle(delayed_delivery, client)  # type: ignore[arg-type]

        assert first_handled is False
        assert first_delivery.acked == 1
        assert len(scheduler.scheduled) == 1
        assert second_handled is True
        assert delayed_delivery.acked == 1
        assert len(worker.processed) == 1

    anyio.run(scenario)


def test_stale_terminal_claim_message_is_acked_not_requeued() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body())
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )
        error = CentralWorkerError(
            "job is already complete",
            status_code=409,
            code="JOB_NOT_RUNNABLE",
        )

        handled = await processor.handle(delivery, FakeClient(error))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert scheduler.scheduled == []

    anyio.run(scenario)


def test_nonretryable_claim_error_is_dead_lettered_without_requeue() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body())
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )
        error = CentralWorkerError(
            "worker key is invalid",
            status_code=403,
            code="INVALID_WORKER_KEY",
        )

        handled = await processor.handle(delivery, FakeClient(error))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 0
        assert delivery.rejected == [False]
        assert scheduler.scheduled == []

    anyio.run(scenario)


def test_case_not_searchable_is_deferred_and_not_dead_lettered() -> None:
    async def scenario() -> None:
        delivery = FakeDelivery(_legacy_event_body())
        scheduler = FakeRetryScheduler()
        processor = RabbitJobProcessor(
            object(),
            retry_scheduler=scheduler,
            retry_delay_seconds=5.0,
            max_retry_attempts=3,
        )
        error = CentralWorkerError(
            "Case is not searchable",
            status_code=422,
            code="CASE_NOT_SEARCHABLE",
        )

        handled = await processor.handle(delivery, FakeClient(error))  # type: ignore[arg-type]

        assert handled is False
        assert delivery.acked == 1
        assert delivery.rejected == []
        assert len(scheduler.scheduled) == 1
        assert scheduler.scheduled[0][1] == 1

    anyio.run(scenario)

