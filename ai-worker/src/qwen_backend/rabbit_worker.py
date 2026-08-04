from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

import aio_pika
import anyio
from pydantic import ValidationError

from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.worker_protocol import RabbitWorkerJobEvent

if TYPE_CHECKING:
    from qwen_backend.notebook_worker import NotebookWorker

logger = logging.getLogger(__name__)


class RabbitDelivery(Protocol):
    body: bytes

    async def ack(self, multiple: bool = False) -> None: ...

    async def reject(self, requeue: bool = False) -> None: ...


class RabbitJobProcessor:
    """Keep one RabbitMQ delivery unacknowledged until a terminal callback succeeds."""

    def __init__(self, worker: NotebookWorker) -> None:
        self._worker = worker

    async def handle(
        self,
        delivery: RabbitDelivery,
        client: CentralWorkerClient,
    ) -> bool:
        try:
            event = RabbitWorkerJobEvent.model_validate_json(delivery.body)
        except ValidationError:
            logger.exception("rejecting malformed recording-analysis RabbitMQ message")
            await delivery.reject(requeue=False)
            return False

        try:
            claim = await client.claim_job(event.job_id)
        except CentralWorkerError:
            logger.exception("central claim failed; requeueing job_id=%d", event.job_id)
            await delivery.reject(requeue=True)
            return False

        if claim.job_id != event.job_id:
            logger.error(
                "claim/event job mismatch claim_job_id=%d event_job_id=%d",
                claim.job_id,
                event.job_id,
            )
            await delivery.reject(requeue=False)
            return False
        if claim.duplicate:
            logger.info("acknowledged already-claimed recording job job_id=%d", event.job_id)
            await delivery.ack()
            return False

        processed = await self._worker.process_claim(client, claim)
        if not processed:
            logger.warning("terminal callback not confirmed; requeueing job_id=%d", event.job_id)
            await delivery.reject(requeue=True)
            return False
        await delivery.ack()
        return True


class RabbitRecordingWorker:
    def __init__(self, worker: NotebookWorker) -> None:
        rabbitmq_url = worker.settings.rabbitmq_url
        if rabbitmq_url is None:
            raise ValueError(
                "RabbitMQ worker requires EYESONU_AI_WORKER_RABBITMQ_URL or RABBITMQ_URL"
            )
        self._worker = worker
        self._rabbitmq_url = rabbitmq_url.get_secret_value()
        self._processor = RabbitJobProcessor(worker)

    async def run_once(self) -> bool:
        async with CentralWorkerClient(
            base_url=self._worker.settings.central_api_url,
            api_key=self._worker.settings.api_key.get_secret_value(),
            worker_id=self._worker.settings.worker_id,
        ) as client:
            connection = await aio_pika.connect_robust(self._rabbitmq_url)
            try:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=self._worker.settings.rabbitmq_prefetch_count)
                queue = await channel.declare_queue(
                    self._worker.settings.rabbitmq_queue,
                    durable=True,
                    passive=True,
                )
                delivery = await queue.get(fail=False)
                if delivery is None:
                    return False
                return await self._processor.handle(delivery, client)
            finally:
                await connection.close()

    async def run_forever(self) -> None:
        while True:
            try:
                await self._consume_until_disconnected()
            except (aio_pika.exceptions.AMQPException, CentralWorkerError, OSError):
                logger.exception(
                    "AI Worker RabbitMQ connection failed; retrying after %.1fs",
                    self._worker.settings.rabbitmq_reconnect_delay_seconds,
                )
                await anyio.sleep(self._worker.settings.rabbitmq_reconnect_delay_seconds)

    async def _consume_until_disconnected(self) -> None:
        async with CentralWorkerClient(
            base_url=self._worker.settings.central_api_url,
            api_key=self._worker.settings.api_key.get_secret_value(),
            worker_id=self._worker.settings.worker_id,
        ) as client:
            connection = await aio_pika.connect_robust(self._rabbitmq_url)
            try:
                channel = await connection.channel()
                await channel.set_qos(prefetch_count=self._worker.settings.rabbitmq_prefetch_count)
                queue = await channel.declare_queue(
                    self._worker.settings.rabbitmq_queue,
                    durable=True,
                    passive=True,
                )
                async with queue.iterator() as iterator:
                    async for delivery in iterator:
                        await self._processor.handle(delivery, client)
            finally:
                await connection.close()
