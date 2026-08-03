from fastapi import FastAPI

from .app_support import authorize_internal_request
from .config import Settings, get_settings
from .main import create_app
from .probability_provenance import (
    ProbabilityRequestReplayGuard,
    load_probability_trust_registry,
)
from .providers import AnalysisProvider
from .zone_search_api import create_zone_search_router


class ResearchRoutesInProductionError(RuntimeError):
    pass


def create_research_app(
    settings: Settings | None = None, provider: AnalysisProvider | None = None
) -> FastAPI:
    active_settings = settings or get_settings()
    if active_settings.environment == "production":
        raise ResearchRoutesInProductionError(
            "search-routing research routes are disabled in production"
        )
    app = create_app(active_settings, provider)
    probability_trust_registry = load_probability_trust_registry(
        active_settings.probability_trust_registry_path
    )
    probability_replay_guard = ProbabilityRequestReplayGuard(
        max_age_seconds=active_settings.probability_request_max_age_seconds,
        future_skew_seconds=active_settings.probability_request_future_skew_seconds,
        cache_size=active_settings.probability_replay_cache_size,
    )
    app.include_router(
        create_zone_search_router(
            lambda provided_key: authorize_internal_request(active_settings, provided_key),
            probability_trust_registry,
            probability_replay_guard,
            active_settings.environment,
            (
                active_settings.probability_evidence_signing_key.get_secret_value()
                if active_settings.probability_evidence_signing_key is not None
                else None
            ),
        )
    )
    return app


app = create_research_app()
