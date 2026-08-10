import pytest
from fastapi.routing import APIRoute

from qwen_backend.config import Settings
from qwen_backend.main import (
    MockProviderInProductionError,
    UnapprovedProductionProviderError,
    create_app,
)
from qwen_backend.providers import MockProvider
from qwen_backend.research_app import (
    ResearchRoutesInProductionError,
    create_research_app,
)
from qwen_backend.schemas import CandidateAnalysisRequest, CandidateAnalysisResponse


def test_production_cannot_start_with_mock_provider() -> None:
    with pytest.raises(
        MockProviderInProductionError,
        match="mock provider is disabled in production",
    ):
        create_app(Settings(provider="mock", environment="production"))


def test_production_cannot_start_with_injected_mock_provider() -> None:
    settings = Settings(provider="qwen", environment="production")
    with pytest.raises(
        MockProviderInProductionError,
        match="mock provider is disabled in production",
    ):
        create_app(settings, provider=MockProvider())


def test_production_rejects_unapproved_injected_provider() -> None:
    class SyntheticProvider:
        model_loaded = True
        model_version = "synthetic-test-provider"

        def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
            raise AssertionError(request)

    settings = Settings(provider="qwen", environment="production")
    with pytest.raises(
        UnapprovedProductionProviderError,
        match="only the configured Qwen3VL provider is allowed in production",
    ):
        create_app(settings, provider=SyntheticProvider())


def test_create_app_preserves_public_route_contract() -> None:
    app = create_app(Settings(provider="mock"))
    public_paths = {
        route.path
        for route in app.routes
        if isinstance(route, APIRoute)
        and (route.path == "/health" or route.path.startswith("/v1/candidates/"))
    }
    assert public_paths == {
        "/health",
        "/v1/candidates/analyze",
        "/v1/candidates/decide",
        "/v1/candidates/decide-with-qwen",
    }
    assert not any(
        isinstance(route, APIRoute) and route.path.startswith("/v1/search-routing/")
        for route in app.routes
    )


def test_research_routes_cannot_start_in_production() -> None:
    with pytest.raises(
        ResearchRoutesInProductionError,
        match="search-routing research routes are disabled in production",
    ):
        create_research_app(Settings(provider="mock", environment="production"))

