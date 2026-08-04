from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Protocol

import aio_pika
import anyio
from pydantic import ValidationError

from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.rabbit_retry import (
    AioPikaRetryScheduler,
    RabbitRetryPolicy,
    RetryScheduler,
    classify_central_error,
)
from qwen_backend.worker_protocol import RabbitWorkerJobEvent

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
    ) -> None:
        self._worker = worker
        self._retry_scheduler = retry_scheduler
        self._retry_policy = RabbitRetryPolicy(retry_delay_seconds, max_retry_attempts)

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

        try:
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
            logger.exception("deferred retry publish failed; requeueing source job_id=%d", job_id)
            await delivery.reject(requeue=True)
            raise RabbitRetryUnavailable("RabbitMQ deferred retry publish failed") from error
        logger.info(
            "deferred recording job job_id=%d retry_count=%d delay_seconds=%.1f reason=%s",
            job_id,
            retry_count,
            delay,
            reason,
        )
        await delivery.ack()


class RabbitRecordingWorker:
    def __init__(self, worker: NotebookWorker) -> None:
        rabbitmq_url = worker.settings.rabbitmq_url
        if rabbitmq_url is None:
            raise ValueError(
                "RabbitMQ worker requires EYESONU_AI_WORKER_RABBITMQ_URL or RABBITMQ_URL"
            )
        self._worker = worker
        self._rabbitmq_url = rabbitmq_url.get_secret_value()

    async def run_once(self) -> bool:
        async with self._client() as client:
            connection = await aio_pika.connect_robust(self._rabbitmq_url)
            try:
                channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
                await channel.set_qos(prefetch_count=self._worker.settings.rabbitmq_prefetch_count)
                queue = await channel.declare_queue(
                    self._worker.settings.rabbitmq_queue,
                    durable=True,
                    passive=True,
                )
                delivery = await queue.get(fail=False)
                if delivery is None:
                    return False
                return await self._processor(channel).handle(delivery, client)
            finally:
                await connection.close()

    async def run_forever(self) -> None:
        while True:
            try:
                await self._consume_until_disconnected()
            except (
                RabbitRetryUnavailable,
                aio_pika.exceptions.AMQPException,
                CentralWorkerError,
                OSError,
                TimeoutError,
            ):
                logger.exception(
                    "AI Worker RabbitMQ connection failed; retrying after %.1fs",
                    self._worker.settings.rabbitmq_reconnect_delay_seconds,
                )
                await anyio.sleep(self._worker.settings.rabbitmq_reconnect_delay_seconds)

    async def _consume_until_disconnected(self) -> None:
        async with self._client() as client:
            connection = await aio_pika.connect_robust(self._rabbitmq_url)
            try:
                channel = await connection.channel(publisher_confirms=True, on_return_raises=True)
                await channel.set_qos(prefetch_count=self._worker.settings.rabbitmq_prefetch_count)
                queue = await channel.declare_queue(
                    self._worker.settings.rabbitmq_queue,
                    durable=True,
                    passive=True,
                )
                processor = self._processor(channel)
                async with queue.iterator() as iterator:
                    async for delivery in iterator:
                        await processor.handle(delivery, client)
            finally:
                await connection.close()

    def _client(self) -> CentralWorkerClient:
        return CentralWorkerClient(
            base_url=self._worker.settings.central_api_url,
            api_key=self._worker.settings.api_key.get_secret_value(),
            worker_id=self._worker.settings.worker_id,
        )

    def _processor(self, channel: aio_pika.abc.AbstractChannel) -> RabbitJobProcessor:
        return RabbitJobProcessor(
            self._worker,
            retry_scheduler=AioPikaRetryScheduler(
                channel,
                exchange_name=self._worker.settings.rabbitmq_retry_exchange,
                routing_key_prefix=self._worker.settings.rabbitmq_retry_routing_key_prefix,
            ),
            retry_delay_seconds=self._worker.settings.rabbitmq_retry_delay_seconds,
            max_retry_attempts=self._worker.settings.rabbitmq_max_retry_attempts,
        )
