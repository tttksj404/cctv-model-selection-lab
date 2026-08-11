from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ProviderName = Literal["mock", "qwen"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="QWEN_", env_file=".env", extra="ignore")

    provider: ProviderName = "mock"
    model_path: Path = Path("<redacted-local-path>")
    model_version: str = "Qwen3-VL-8B-Instruct"
    max_new_tokens: int = Field(default=128, ge=1, le=512)
    device_map: str = "auto"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
