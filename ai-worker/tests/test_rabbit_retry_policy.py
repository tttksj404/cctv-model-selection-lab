from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from qwen_backend import rabbit_retry
from qwen_backend.central_client import CentralWorkerError
from qwen_backend.notebook_worker import NotebookWorkerSettings
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


def test_case_not_searchable_is_deferred_until_the_case_is_activated() -> None:
    assert classify_central_error(
        CentralWorkerError(
            "Case is not searchable",
            status_code=422,
            code="CASE_NOT_SEARCHABLE",
        )
    ) == "RETRY"


def test_active_lease_delay_is_bounded_by_the_largest_declared_retry_bucket() -> None:
    policy = RabbitRetryPolicy(retry_delay_seconds=5.0, max_retry_attempts=20)

    delay = policy.active_lease_delay(datetime.now(UTC) + timedelta(hours=1))

    assert delay == 300.0


def test_retry_schedule_selects_the_first_configured_bucket_that_can_hold_the_delay() -> None:
    schedule = rabbit_retry.RabbitRetrySchedule((7, 11, 45))

    assert schedule.bucket_for(7.0) == 7
    assert schedule.bucket_for(7.1) == 11
    assert schedule.bucket_for(99.0) == 45
    assert schedule.max_delay_seconds == 45.0


def test_notebook_worker_settings_parse_retry_bucket_list_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("EYESONU_AI_WORKER_RABBITMQ_RETRY_DELAY_BUCKETS_SECONDS", "7,11,45")

    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="test-key",
    )

    assert settings.rabbitmq_retry_delay_buckets_seconds == (7, 11, 45)
