from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Header
from fastapi.responses import JSONResponse

from .probability_provenance import (
    Environment,
    ProbabilityRequestReplayGuard,
    ProbabilityTrustRegistry,
    ReplayedProbabilityRequest,
    UntrustedProbabilityProvenance,
    validate_probability_provenance,
)
from .zone_probability import assess_zone_probability
from .zone_probability_schemas import ZoneProbabilityRequest, ZoneProbabilityResponse
from .zone_search_policy import (
    build_candidate_event_directive,
    build_operator_decision_directive,
    build_zone_search_plan,
)
from .zone_search_schemas import (
    CandidateEventDirective,
    CandidateEventRequest,
    OperatorDecisionDirective,
    OperatorDecisionRequest,
    ZoneSearchPlanRequest,
    ZoneSearchPlanResponse,
)

AuthorizationCheck = Callable[[str | None], JSONResponse | None]


def create_zone_search_router(
    authorize: AuthorizationCheck,
    trust_registry: ProbabilityTrustRegistry,
    replay_guard: ProbabilityRequestReplayGuard,
    environment: Environment,
    evidence_signing_key: str | None,
) -> APIRouter:
    router = APIRouter(prefix="/v1/search-routing", tags=["search-routing"])

    @router.post("/plan", response_model=ZoneSearchPlanResponse)
    async def plan(
        request: ZoneSearchPlanRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> ZoneSearchPlanResponse | JSONResponse:
        authorization_error = authorize(x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        return build_zone_search_plan(request)

    @router.post("/probability", response_model=ZoneProbabilityResponse)
    async def probability(
        request: ZoneProbabilityRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> ZoneProbabilityResponse | JSONResponse:
        authorization_error = authorize(x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        try:
            validate_probability_provenance(
                request,
                trust_registry,
                environment,
                evidence_signing_key,
            )
        except UntrustedProbabilityProvenance:
            return JSONResponse(
                status_code=422,
                content={
                    "code": "untrusted_probability_provenance",
                    "message": "probability provenance is not trusted",
                },
            )
        try:
            replay_guard.consume(request)
        except ReplayedProbabilityRequest:
            return JSONResponse(
                status_code=409,
                content={
                    "code": "replayed_or_stale_probability_request",
                    "message": "probability request is expired, duplicated, or stale",
                },
            )
        return assess_zone_probability(request)

    @router.post("/candidate-events", response_model=CandidateEventDirective)
    async def candidate_event(
        request: CandidateEventRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> CandidateEventDirective | JSONResponse:
        authorization_error = authorize(x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        return build_candidate_event_directive(request)

    @router.post("/operator-decision", response_model=OperatorDecisionDirective)
    async def operator_decision(
        request: OperatorDecisionRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> OperatorDecisionDirective | JSONResponse:
        authorization_error = authorize(x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        return build_operator_decision_directive(request)

    return router

