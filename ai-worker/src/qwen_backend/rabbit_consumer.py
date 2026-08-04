from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import aio_pika
import anyio

from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.rabbit_retry import AioPikaRetryScheduler, RabbitRetrySchedule
from qwen_backend.rabbit_worker import RabbitJobProcessor, RabbitRetryUnavailable

if TYPE_CHECKING:
    from qwen_backend.notebook_worker import NotebookWorker

logger = logging.getLogger(__name__)


class RabbitRecordingWorker:
    """Own RabbitMQ connection lifecycle for one notebook-local recording worker."""

    def __init__(self, worker: NotebookWorker) -> None:
        rabbitmq_url = worker.settings.rabbitmq_url
        if rabbitmq_url is None:
            raise ValueError(
                "RabbitMQ worker requires EYESONU_AI_WORKER_RABBITMQ_URL or RABBITMQ_URL"
            )
        self._worker = worker
        self._rabbitmq_url = rabbitmq_url.get_secret_value()
        self._retry_schedule = RabbitRetrySchedule(
            worker.settings.rabbitmq_retry_delay_buckets_seconds
        )

    async def run_once(self) -> bool:
        """Consume at most one passive-queue delivery for local smoke testing."""

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
        """Reconnect after broker or central transport failures without losing source ACK safety."""

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
                retry_schedule=self._retry_schedule,
            ),
            retry_delay_seconds=self._worker.settings.rabbitmq_retry_delay_seconds,
            max_retry_attempts=self._worker.settings.rabbitmq_max_retry_attempts,
            retry_schedule=self._retry_schedule,
        )
