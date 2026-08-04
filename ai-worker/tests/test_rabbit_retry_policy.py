from __future__ import annotations

from datetime import UTC, datetime, timedelta

from qwen_backend.central_client import CentralWorkerError
from qwen_backend.rabbit_retry import RabbitRetryPolicy, classify_central_error


def test_only_transient_central_errors_are_retried() -> None:
    assert classify_central_error(
        CentralWorkerError("central unavailable", status_code=503, code="UPSTREAM_ERROR")
    ) == "RETRY"
    assert classify_central_error(CentralWorkerError("timeout")) == "RETRY"
    assert classify_central_error(
        CentralWorkerError("invalid worker key", status_code=403, code="INVALID_WORKER_KEY")
    ) == "DEAD_LETTER"
    assert classify_central_error(
        CentralWorkerError("already complete", status_code=409, code="JOB_NOT_RUNNABLE")
    ) == "ACK"


def test_active_lease_delay_is_bounded_by_the_largest_declared_retry_bucket() -> None:
    policy = RabbitRetryPolicy(retry_delay_seconds=5.0, max_retry_attempts=20)

    delay = policy.active_lease_delay(datetime.now(UTC) + timedelta(hours=1))

    assert delay == 300.0
