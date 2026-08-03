from __future__ import annotations

import hmac

from fastapi.responses import JSONResponse

from .config import Settings
from .providers import AnalysisProvider, MockProvider, Qwen3VLProvider
from .schemas import ErrorResponse


class MockProviderInProductionError(RuntimeError):
    pass


class UnapprovedProductionProviderError(RuntimeError):
    pass


def build_provider(settings: Settings) -> AnalysisProvider:
    if settings.provider == "mock":
        if settings.environment == "production":
            raise MockProviderInProductionError("mock provider is disabled in production")
        return MockProvider()
    return Qwen3VLProvider(settings)


def authorize_internal_request(
    settings: Settings,
    provided_key: str | None,
) -> JSONResponse | None:
    if settings.internal_api_key is None:
        return JSONResponse(
            status_code=503,
            content=ErrorResponse(
                code="service_misconfigured",
                message="QWEN_INTERNAL_API_KEY must be configured for protected APIs",
            ).model_dump(),
        )
    if provided_key is None or not hmac.compare_digest(provided_key, settings.internal_api_key):
        return JSONResponse(
            status_code=401,
            content=ErrorResponse(
                code="unauthorized",
                message="internal API key is required",
            ).model_dump(),
        )
    return None
