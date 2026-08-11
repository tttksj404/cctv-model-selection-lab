from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["mock", "qwen"]
EnvironmentName = Literal["development", "test", "production"]
DEFAULT_PROBABILITY_TRUST_REGISTRY = (
    Path(__file__).with_name("resources") / "zone_probability_trust_registry.json"
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QWEN_", env_file=".env", extra="ignore")

    provider: ProviderName = "mock"
    environment: EnvironmentName = "development"
    model_path: Path = Path("<redacted-local-path>")
    image_root: Path = Path.cwd()
    model_version: str = "Qwen3-VL-8B-Instruct"
    max_new_tokens: int = Field(default=256, ge=1, le=512)
    device_map: str = "auto"
    internal_api_key: str | None = Field(default=None, min_length=1)
    inference_concurrency: int = Field(default=2, ge=1, le=16)
    inference_queue_timeout_ms: int = Field(default=500, ge=1, le=10000)
    florence_enabled: bool = False
    florence_model_path: Path = Path("<redacted-local-path>")
    florence_model_version: str = "microsoft/Florence-2-large"
    florence_max_new_tokens: int = Field(default=128, ge=1, le=512)
    florence_device_map: str = "auto"
    florence_attribute_prompt_version: str = "florence-attributes-v1"
    server_attribute_enabled: bool = False
    server_attribute_manifest_path: Path = Path("training/solider_server_attribute_candidate.json")
    server_attribute_workspace: Path = Path.cwd()
    probability_trust_registry_path: Path = DEFAULT_PROBABILITY_TRUST_REGISTRY
    probability_evidence_signing_key: SecretStr | None = Field(default=None, min_length=32)
    probability_request_max_age_seconds: int = Field(default=300, ge=30, le=3_600)
    probability_request_future_skew_seconds: int = Field(default=30, ge=0, le=300)
    probability_replay_cache_size: int = Field(default=10_000, ge=100, le=100_000)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
