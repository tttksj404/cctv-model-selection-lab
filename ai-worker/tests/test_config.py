import pytest
from pydantic import ValidationError

from qwen_backend.config import Settings


def test_server_binding_is_configurable() -> None:
    settings = Settings(
        _env_file=None,
        server_host="0.0.0.0",
        server_port=9_001,
    )

    assert settings.server_host == "0.0.0.0"
    assert settings.server_port == 9_001


def test_server_port_rejects_out_of_range_value() -> None:
    with pytest.raises(ValidationError, match="server_port"):
        Settings(_env_file=None, server_port=65_536)


def test_internal_api_key_rejects_placeholder() -> None:
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(_env_file=None, internal_api_key="change-me")
