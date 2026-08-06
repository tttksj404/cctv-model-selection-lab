from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

import aio_pika
import anyio
from pydantic import ValidationError

from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.rabbit_retry import (
    DEFAULT_RABBIT_RETRY_SCHEDULE,
    RabbitRetryPolicy,
    RabbitRetrySchedule,
    RetryScheduler,
    classify_central_error,
)
from qwen_backend.worker_protocol import RabbitWorkerJobEvent
from qwen_backend.worker_status import NullWorkerStatus, WorkerStage, WorkerStatusSink

if TYPE_CHECKING:
    from qwen_backend.notebook_worker import NotebookWorker

logger = logging.getLogger(__name__)


class RabbitRetryUnavailable(RuntimeError):
    """A deferred retry could not be confirmed by RabbitMQ."""


class RabbitDelivery(Protocol):
    body: bytes

    @property
    def headers(self) -> Mapping[str, object]: ...

    async def ack(self, multiple: bool = False) -> None: ...

    async def reject(self, requeue: bool = False) -> None: ...


class RabbitJobProcessor:
    """Keep deliveries until terminal processing or durable deferred retry succeeds."""

    def __init__(
        self,
        worker: NotebookWorker,
        *,
        retry_scheduler: RetryScheduler,
        retry_delay_seconds: float,
        max_retry_attempts: int,
        retry_schedule: RabbitRetrySchedule = DEFAULT_RABBIT_RETRY_SCHEDULE,
        status: WorkerStatusSink | None = None,
    ) -> None:
        self._worker = worker
        self._retry_scheduler = retry_scheduler
        self._retry_policy = RabbitRetryPolicy(
            retry_delay_seconds,
            max_retry_attempts,
            retry_schedule,
        )
        self._status = status or NullWorkerStatus()

    async def handle(
        self,
        delivery: RabbitDelivery,
        client: CentralWorkerClient,
    ) -> bool:
        try:
            event = RabbitWorkerJobEvent.model_validate_json(delivery.body)
        except ValidationError:
            logger.exception("dead-lettering malformed recording-analysis RabbitMQ message")
            await delivery.reject(requeue=False)
            return False

        self._status.update(
            WorkerStage.RECEIVED,
            "백엔드에서 녹화 분석 작업을 수신함",
            job_id=event.job_id,
        )

        if getattr(client, "uses_current_device_api", False):
            return await self._handle_current_device_event(delivery, client, event)
        if getattr(client, "uses_device_key", False):
            return await self._handle_device_event(delivery, client, event)

        try:
            self._status.update(
                WorkerStage.CLAIMING,
                "작업을 이 워커에 점유하는 중",
                job_id=event.job_id,
            )
            claim = await client.claim_job(event.job_id)
        except ValidationError:
            logger.exception(
                "dead-lettering invalid central claim response job_id=%d",
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False
        except CentralWorkerError as error:
            return await self._handle_central_error(delivery, event.job_id, error, "claim")

        if claim.job_id != event.job_id:
            logger.error(
                "claim/event job mismatch claim_job_id=%d event_job_id=%d",
                claim.job_id,
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False
        if claim.disposition in {"LEASE_HELD", "LEASE_HELD_BY_SELF", "LEASE_HELD_BY_OTHER"}:
            lease_owner = {
                "LEASE_HELD_BY_SELF": "this worker",
                "LEASE_HELD_BY_OTHER": "another worker",
            }.get(claim.disposition, "an unknown legacy worker")
            await self._defer(
                delivery,
                job_id=event.job_id,
                reason=f"active lease held by {lease_owner}",
                delay_seconds=self._retry_policy.active_lease_delay(claim.claim_expires_at),
                consume_retry_budget=False,
            )
            return False
        if claim.disposition == "RETRY_PENDING":
            await self._defer(
                delivery,
                job_id=event.job_id,
                reason="job became queued concurrently",
                consume_retry_budget=False,
            )
            return False
        if claim.disposition == "TERMINAL":
            logger.info("acknowledging stale terminal recording job job_id=%d", event.job_id)
            await delivery.ack()
            return False

        try:
            processed = await self._worker.process_claim(client, claim)
        except CentralWorkerError as error:
            return await self._handle_central_error(delivery, event.job_id, error, "processing")
        if not processed:
            logger.warning("terminal callback not confirmed; deferring job_id=%d", event.job_id)
            await self._defer(delivery, job_id=event.job_id, reason="terminal callback unconfirmed")
            return False
        await delivery.ack()
        return True

    async def _handle_current_device_event(
        self,
        delivery: RabbitDelivery,
        client: CentralWorkerClient,
        event: RabbitWorkerJobEvent,
    ) -> bool:
        """Claim and process one job using the current `/device/ai/jobs` API.

        The current backend claim endpoint intentionally selects the oldest
        claimable job and therefore does not take the Rabbit event's job ID.
        The event is a durable wake-up signal; the returned claim is the
        authoritative job identity.
        """

        try:
            self._status.update(
                WorkerStage.CLAIMING,
                "AI 검색 작업을 중앙 서버에서 임대하는 중",
                job_id=event.job_id,
            )
            claimed = await client.claim_device_job(self._worker.settings.model_key)
        except CentralWorkerError as error:
            return await self._handle_central_error(delivery, event.job_id, error, "device claim")
        except (TypeError, ValueError):
            logger.exception(
                "dead-lettering invalid current Device API claim job_id=%d",
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False

        if claimed is None:
            logger.info(
                "acknowledging stale AI search wake-up with no claimable job_id=%d",
                event.job_id,
            )
            await delivery.ack()
            return False
        if claimed.job_id != event.job_id:
            logger.info(
                "Rabbit wake-up job_id=%d claimed authoritative job_id=%d",
                event.job_id,
                claimed.job_id,
            )

        while claimed is not None:
            try:
                processed = await self._worker.process_device_claim(client, claimed)
            except CentralWorkerError as error:
                return await self._handle_central_error(
                    delivery,
                    claimed.job_id,
                    error,
                    "device processing",
                )
            except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError):
                logger.exception(
                    "dead-lettering invalid current Device API recording job job_id=%d",
                    claimed.job_id,
                )
                await delivery.reject(requeue=False)
                return False
            if not processed:
                logger.warning(
                    "current Device API result was not confirmed; deferring job_id=%d",
                    claimed.job_id,
                )
                await self._defer(
                    delivery,
                    job_id=claimed.job_id,
                    reason="device result unconfirmed",
                )
                return False

            # The Rabbit event is a wake-up signal, while the Device API claim
            # endpoint is the FIFO authority.  Drain all jobs that are already
            # queued before returning to RabbitMQ so a later event cannot jump
            # ahead of older central-server work.
            try:
                claimed = await client.claim_device_job(self._worker.settings.model_key)
            except CentralWorkerError as error:
                return await self._handle_central_error(
                    delivery,
                    claimed.job_id,
                    error,
                    "device drain claim",
                )
            except (TypeError, ValueError):
                logger.exception(
                    "dead-lettering invalid current Device API drain claim"
                )
                await delivery.reject(requeue=False)
                return False
        await delivery.ack()
        return True

    async def _handle_device_event(
        self,
        delivery: RabbitDelivery,
        client: CentralWorkerClient,
        event: RabbitWorkerJobEvent,
    ) -> bool:
        """Process the pre-Worker-API enriched event without an internal claim.

        The old dev publisher puts the recording target in the message and the
        central Rabbit consumer owns the database claim.  A routing-only event
        cannot be processed with only a Device Key, so it is dead-lettered with
        an explicit contract error instead of accidentally calling the
        ``X-Worker-Key`` API.
        """

        required = (
            event.case_id,
            event.recording_id,
            event.camera_id,
            event.camera_code,
            event.camera_name,
            event.recording_object_key,
            event.prompt,
        )
        if any(value is None for value in required):
            logger.error(
                "dead-lettering routing-only event in Device Key mode; "
                "legacy target fields are required job_id=%d",
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False

        try:
            processed = await self._worker.process_device_event(client, event)
        except CentralWorkerError as error:
            return await self._handle_central_error(
                delivery,
                event.job_id,
                error,
                "device processing",
            )
        except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError):
            logger.exception(
                "dead-lettering invalid Device Key recording job job_id=%d",
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False
        if not processed:
            logger.warning("Device Key result was not confirmed; deferring job_id=%d", event.job_id)
            await self._defer(delivery, job_id=event.job_id, reason="device result unconfirmed")
            return False
        await delivery.ack()
        return True

    async def _handle_central_error(
        self,
        delivery: RabbitDelivery,
        job_id: int,
        error: CentralWorkerError,
        operation: str,
    ) -> bool:
        action = classify_central_error(error)
        if action == "ACK":
            logger.info(
                "acknowledging stale central response job_id=%d operation=%s code=%s",
                job_id,
                operation,
                error.code,
            )
            await delivery.ack()
            return False
        if action == "DEAD_LETTER":
            logger.warning(
                "dead-lettering non-retryable central error job_id=%d operation=%s code=%s",
                job_id,
                operation,
                error.code,
            )
            await delivery.reject(requeue=False)
            return False
        logger.warning(
            "deferring retryable central error job_id=%d operation=%s code=%s",
            job_id,
            operation,
            error.code,
        )
        await self._defer(delivery, job_id=job_id, reason=f"retryable central {operation} error")
        return False

    async def _defer(
        self,
        delivery: RabbitDelivery,
        *,
        job_id: int,
        reason: str,
        delay_seconds: float | None = None,
        consume_retry_budget: bool = True,
    ) -> None:
        if consume_retry_budget:
            retry_count = self._retry_policy.next_retry_count(delivery.headers)
            if retry_count is None:
                logger.error(
                    "dead-lettering exhausted deferred retry job_id=%d reason=%s",
                    job_id,
                    reason,
                )
                await delivery.reject(requeue=False)
                return
        else:
            retry_count = self._retry_policy.current_retry_count(delivery.headers)
        delay = delay_seconds or self._retry_policy.transient_delay(retry_count)
        try:
            await self._retry_scheduler.schedule(
                delivery.body,
                retry_count=retry_count,
                delay_seconds=delay,
            )
        except (aio_pika.exceptions.AMQPException, OSError, TimeoutError) as error:
            logger.exception("deferred retry publish failed; recovering source job_id=%d", job_id)
            try:
                await delivery.reject(requeue=True)
            except (
                aio_pika.exceptions.AMQPException,
                aio_pika.exceptions.ChannelInvalidStateError,
                OSError,
                TimeoutError,
            ) as reject_error:
                logger.warning(
                    "source delivery requeue unavailable; broker will recover unacked job_id=%d "
                    "error_type=%s",
                    job_id,
                    type(reject_error).__name__,
                )
                await anyio.sleep(delay)
            raise RabbitRetryUnavailable("RabbitMQ deferred retry publish failed") from error
        logger.info(
            "deferred recording job job_id=%d retry_count=%d delay_seconds=%.1f reason=%s",
            job_id,
            retry_count,
            delay,
            reason,
        )
        await delivery.ack()
