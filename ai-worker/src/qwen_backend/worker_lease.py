from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

import anyio

from qwen_backend.central_client import CentralWorkerError
from qwen_backend.worker_protocol import RecordingAnalysisWorkerHeartbeat

logger = logging.getLogger(__name__)


class LeaseLostError(RuntimeError):
    """The central server no longer accepts this worker's terminal callback."""


class LeaseHeartbeatClient(Protocol):
    """Central API operation required to retain one claimed job lease."""

    async def heartbeat(
        self,
        job_id: int,
        claim_token: str,
    ) -> RecordingAnalysisWorkerHeartbeat: ...


@dataclass(frozen=True, slots=True)
class LeaseHeartbeatContext:
    """Mutable lifecycle signals paired with one immutable worker lease identity."""

    client: LeaseHeartbeatClient
    job_id: int
    lease_token: str
    interval_seconds: float
    stop: anyio.Event
    lease_lost: anyio.Event
    fatal_errors: list[CentralWorkerError]


async def maintain_lease(context: LeaseHeartbeatContext) -> None:
    """Heartbeat until local completion or a central lease failure."""

    while not context.stop.is_set():
        with anyio.move_on_after(context.interval_seconds) as scope:
            await context.stop.wait()
        if not scope.cancel_called:
            return
        try:
            await context.client.heartbeat(context.job_id, context.lease_token)
        except CentralWorkerError as error:
            context.lease_lost.set()
            logger.exception("AI Worker heartbeat failed job_id=%d", context.job_id)
            if (
                not error.is_lease_conflict
                and error.status_code is not None
                and 400 <= error.status_code < 500
            ):
                context.fatal_errors.append(error)
            return


def raise_if_lease_lost(
    lease_lost: anyio.Event,
    job_id: int,
    fatal_errors: list[CentralWorkerError],
) -> None:
    """Convert heartbeat signals into the terminal processing outcome."""

    if fatal_errors:
        raise fatal_errors[0]
    if lease_lost.is_set():
        raise LeaseLostError(f"lease lost for job {job_id}")
