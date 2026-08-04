from __future__ import annotations

import socket
from pathlib import Path
from typing import Annotated, Final
from urllib.parse import urlsplit

from pydantic import AliasChoices, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_MODEL_KEY: Final = "hybrid-solider-clip-v1"
DEFAULT_HEARTBEAT_INTERVAL_SECONDS: Final = 20.0
DEFAULT_RABBITMQ_QUEUE: Final = "search.target.recording.queue"
DEFAULT_RABBITMQ_RECONNECT_DELAY_SECONDS: Final = 5.0
DEFAULT_RABBITMQ_RETRY_EXCHANGE: Final = "search.target.recording.retry.exchange"
DEFAULT_RABBITMQ_RETRY_ROUTING_KEY_PREFIX: Final = "search.target.recording.retry"
DEFAULT_RABBITMQ_RETRY_DELAY_SECONDS: Final = 5.0
DEFAULT_RABBITMQ_RETRY_DELAY_BUCKETS_SECONDS: Final = (5, 15, 30, 60, 300)
DEFAULT_RABBITMQ_MAX_RETRY_ATTEMPTS: Final = 20
DEFAULT_MAX_DOWNLOAD_BYTES: Final = 5 * 1024 * 1024 * 1024
DEFAULT_MAX_EVIDENCE_UPLOAD_BYTES: Final = 10 * 1024 * 1024


class NotebookWorkerSettings(BaseSettings):
    """Notebook-local configuration for a RabbitMQ-driven recording worker."""

    model_config = SettingsConfigDict(
        env_prefix="EYESONU_AI_WORKER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    central_api_url: str = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_CENTRAL_API_URL",
            "CENTRAL_API_BASE_URL",
        ),
    )
    api_key: SecretStr = Field(
        min_length=1,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_API_KEY",
            "CENTRAL_API_WORKER_KEY",
        ),
    )
    worker_id: str = Field(
        default_factory=lambda: f"notebook-{socket.gethostname()}",
        min_length=1,
        max_length=100,
    )
    model_key: str = Field(default=DEFAULT_MODEL_KEY, min_length=1, max_length=100)
    heartbeat_interval_seconds: float = Field(
        default=DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
        gt=0.5,
        le=300.0,
    )
    rabbitmq_url: SecretStr | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_URL",
            "RABBITMQ_URL",
        ),
    )
    rabbitmq_queue: str = Field(
        default=DEFAULT_RABBITMQ_QUEUE,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_QUEUE",
            "RABBITMQ_QUEUE",
        ),
    )
    rabbitmq_prefetch_count: int = Field(default=1, ge=1, le=1)
    rabbitmq_reconnect_delay_seconds: float = Field(
        default=DEFAULT_RABBITMQ_RECONNECT_DELAY_SECONDS,
        gt=0.1,
        le=300.0,
    )
    rabbitmq_retry_exchange: str = Field(
        default=DEFAULT_RABBITMQ_RETRY_EXCHANGE,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_RETRY_EXCHANGE",
            "RABBITMQ_RETRY_EXCHANGE",
        ),
    )
    rabbitmq_retry_routing_key_prefix: str = Field(
        default=DEFAULT_RABBITMQ_RETRY_ROUTING_KEY_PREFIX,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$",
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_RETRY_ROUTING_KEY_PREFIX",
            "RABBITMQ_RETRY_ROUTING_KEY_PREFIX",
            "EYESONU_AI_WORKER_RABBITMQ_RETRY_ROUTING_KEY",
            "RABBITMQ_RETRY_ROUTING_KEY",
        ),
    )
    rabbitmq_retry_delay_seconds: float = Field(
        default=DEFAULT_RABBITMQ_RETRY_DELAY_SECONDS,
        gt=0.1,
        le=300.0,
    )
    rabbitmq_retry_delay_buckets_seconds: Annotated[tuple[int, ...], NoDecode] = Field(
        default=DEFAULT_RABBITMQ_RETRY_DELAY_BUCKETS_SECONDS,
        validation_alias=AliasChoices(
            "EYESONU_AI_WORKER_RABBITMQ_RETRY_DELAY_BUCKETS_SECONDS",
            "RABBITMQ_RETRY_DELAY_BUCKETS_SECONDS",
        ),
    )
    rabbitmq_max_retry_attempts: int = Field(
        default=DEFAULT_RABBITMQ_MAX_RETRY_ATTEMPTS,
        ge=1,
        le=100,
    )
    cache_dir: Path = Path("artifacts/ai-worker/cache")
    output_dir: Path = Path("artifacts/ai-worker/jobs")
    max_download_bytes: int = Field(default=DEFAULT_MAX_DOWNLOAD_BYTES, gt=0, le=50 * 1024**3)
    max_evidence_upload_bytes: int = Field(
        default=DEFAULT_MAX_EVIDENCE_UPLOAD_BYTES,
        gt=0,
        le=100 * 1024 * 1024,
    )

    @field_validator("central_api_url")
    @classmethod
    def validate_central_api_url(cls, value: str) -> str:
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("central API URL must use http or https")
        return normalized

    @field_validator("api_key")
    @classmethod
    def reject_placeholder_api_key(cls, value: SecretStr) -> SecretStr:
        normalized = value.get_secret_value().strip().lower()
        if normalized in {
            "inject-from-local-secret-store",
            "change-me",
            "changeme",
            "replace-me",
        }:
            raise ValueError("AI Worker API key must not be a placeholder")
        return value

    @field_validator("rabbitmq_url")
    @classmethod
    def validate_rabbitmq_url(cls, value: SecretStr | None) -> SecretStr | None:
        if value is None:
            return None
        normalized = value.get_secret_value().strip()
        if not normalized:
            return None
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"amqp", "amqps"} or not parsed.hostname:
            raise ValueError("RabbitMQ URL must use amqp or amqps with a host")
        if normalized.lower() in {
            "inject-from-local-secret-store",
            "change-me",
            "changeme",
            "replace-me",
        }:
            raise ValueError("RabbitMQ URL must not be a placeholder")
        return SecretStr(normalized)

    @field_validator("rabbitmq_retry_delay_buckets_seconds", mode="before")
    @classmethod
    def parse_retry_delay_buckets(
        cls,
        value: str | list[int] | tuple[int, ...],
    ) -> tuple[int, ...]:
        buckets = (
            tuple(int(item.strip()) for item in value.split(",") if item.strip())
            if isinstance(value, str)
            else tuple(value)
        )
        if not buckets or any(bucket <= 0 for bucket in buckets):
            raise ValueError("RabbitMQ retry delay buckets must contain positive seconds")
        if tuple(sorted(set(buckets))) != buckets:
            raise ValueError("RabbitMQ retry delay buckets must be unique and ascending")
        return buckets
