from __future__ import annotations

import pytest
from auth_support import TEST_INTERNAL_API_KEY


@pytest.fixture(autouse=True)
def configure_test_internal_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QWEN_INTERNAL_API_KEY", TEST_INTERNAL_API_KEY)

