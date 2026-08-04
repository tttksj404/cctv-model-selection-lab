from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, Literal, Protocol

import aio_pika

from qwen_backend.central_client import CentralWorkerError

RETRY_COUNT_HEADER = "x-eyesonu-retry-count"
ClaimErrorAction = Literal["ACK", "DEAD_LETTER", "RETRY"]
_RETRY_DELAY_BUCKET_SECONDS: Final[tuple[int, ...]] = (5, 15, 30, 60, 300)
MAX_RETRY_DELAY_SECONDS: Final[float] = float(_RETRY_DELAY_BUCKET_SECONDS[-1])


class RetryScheduler(Protocol):
    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None: ...


class AioPikaRetryScheduler:
    """Publishes one persistent, TTL-delayed copy before the source is ACKed."""

    def __init__(
        self,
        channel: aio_pika.abc.AbstractChannel,
        *,
        exchange_name: str,
        routing_key_prefix: str,
    ) -> None:
        self._channel = channel
        self._exchange_name = exchange_name
        self._routing_key_prefix = routing_key_prefix

    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        if retry_count < 0:
            raise ValueError("retry_count must not be negative")
        if delay_seconds <= 0:
            raise ValueError("delay_seconds must be positive")
        exchange = await self._channel.get_exchange(self._exchange_name, ensure=False)
        bucket_seconds = retry_delay_bucket_seconds(delay_seconds)
        message = aio_pika.Message(
            body,
            headers={RETRY_COUNT_HEADER: retry_count},
            content_type="application/json",
            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
        )
        await exchange.publish(
            message,
            f"{self._routing_key_prefix}.{bucket_seconds}s",
            mandatory=True,
        )


@dataclass(frozen=True)
class RabbitRetryPolicy:
    retry_delay_seconds: float
    max_retry_attempts: int
    max_transient_delay_seconds: float = 300.0
    max_lease_delay_seconds: float = MAX_RETRY_DELAY_SECONDS

    def __post_init__(self) -> None:
        if self.retry_delay_seconds <= 0:
            raise ValueError("retry_delay_seconds must be positive")
        if self.max_retry_attempts < 1:
            raise ValueError("max_retry_attempts must be positive")

    def next_retry_count(self, headers: Mapping[str, object]) -> int | None:
        previous = self.current_retry_count(headers)
        if previous >= self.max_retry_attempts:
            return None
        return previous + 1

    def current_retry_count(self, headers: Mapping[str, object]) -> int:
        """Return the transient failure budget already spent by this delivery."""

        return _retry_count(headers)

    def transient_delay(self, retry_count: int) -> float:
        exponent = min(max(retry_count - 1, 0), 6)
        return min(
            self.retry_delay_seconds * (2**exponent),
            self.max_transient_delay_seconds,
        )

    def active_lease_delay(self, claim_expires_at: datetime | None) -> float:
        if claim_expires_at is None or claim_expires_at.tzinfo is None:
            return self.retry_delay_seconds
        remaining = (claim_expires_at.astimezone(UTC) - datetime.now(UTC)).total_seconds() + 1.0
        return min(
            max(self.retry_delay_seconds, remaining),
            self.max_lease_delay_seconds,
        )


def classify_central_error(error: CentralWorkerError) -> ClaimErrorAction:
    """Retry only transient central failures; stale or invalid work must leave the queue."""

    if error.code == "JOB_NOT_RUNNABLE":
        return "ACK"
    if error.status_code is not None and 400 <= error.status_code < 500:
        return "DEAD_LETTER"
    return "RETRY"


def retry_delay_bucket_seconds(delay_seconds: float) -> int:
    for bucket_seconds in _RETRY_DELAY_BUCKET_SECONDS:
        if delay_seconds <= bucket_seconds:
            return bucket_seconds
    return _RETRY_DELAY_BUCKET_SECONDS[-1]


def _retry_count(headers: Mapping[str, object]) -> int:
    value = headers.get(RETRY_COUNT_HEADER, 0)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return 0
    return value
