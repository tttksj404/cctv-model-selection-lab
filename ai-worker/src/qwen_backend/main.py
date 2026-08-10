import logging
from collections.abc import Callable
from typing import TypeVar

from anyio import CapacityLimiter, fail_after, to_thread
from fastapi import FastAPI, Header
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.requests import Request

from .app_support import (
    MockProviderInProductionError,
    UnapprovedProductionProviderError,
    authorize_internal_request,
    build_provider,
)
from .config import Settings, get_settings
from .decision_engine import review_on_provider_failure
from .decision_gate import (
    decide_candidates_for_retrieval_only_api as decide_candidates,
)
from .decision_gate import (
    enforce_retrieval_only_analysis,
)
from .decision_schemas import (
    DecisionRequest,
    DecisionResponse,
    QwenDecisionRequest,
)
from .providers import (
    AnalysisProvider,
    MockProvider,
    ProviderInferenceError,
    ProviderUnavailable,
    Qwen3VLProvider,
)
from .qwen_decision import decide_with_qwen_candidates
from .schemas import (
    CandidateAnalysisRequest,
    CandidateAnalysisResponse,
    ErrorResponse,
    HealthResponse,
    validate_local_image,
)
from .solider_artifact import inspect_solider_readiness

logger = logging.getLogger(__name__)
_InferenceResult = TypeVar("_InferenceResult")


class InferenceQueueTimeout(RuntimeError):
    pass


def create_app(
    settings: Settings | None = None, provider: AnalysisProvider | None = None
) -> FastAPI:
    active_settings = settings or get_settings()
    active_provider = provider or build_provider(active_settings)
    if active_settings.environment == "production":
        if isinstance(active_provider, MockProvider):
            raise MockProviderInProductionError("mock provider is disabled in production")
        if not isinstance(active_provider, Qwen3VLProvider):
            raise UnapprovedProductionProviderError(
                "only the configured Qwen3VL provider is allowed in production"
            )
    inference_limiter = CapacityLimiter(active_settings.inference_concurrency)
    app = FastAPI(title="Qwen3-VL Candidate Analyzer", version="0.1.0")

    async def run_inference(function: Callable[[], _InferenceResult]) -> _InferenceResult:
        try:
            with fail_after(active_settings.inference_queue_timeout_ms / 1000):
                return await to_thread.run_sync(
                    function,
                    abandon_on_cancel=True,
                    limiter=inference_limiter,
                )
        except TimeoutError as exc:
            raise InferenceQueueTimeout from exc

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="validation_error", message="request validation failed"
            ).model_dump(),
        )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        synthetic_provider = isinstance(active_provider, MockProvider)
        attribute_readiness = inspect_solider_readiness(
            active_settings.server_attribute_manifest_path,
            active_settings.server_attribute_workspace,
        )
        return HealthResponse(
            status=(
                "degraded"
                if synthetic_provider
                or not active_provider.model_loaded
                or (
                    active_settings.server_attribute_enabled
                    and not attribute_readiness.server_attribute_ready
                )
                else "ok"
            ),
            provider=active_settings.provider,
            modelLoaded=active_provider.model_loaded and not synthetic_provider,
            modelVersion=active_provider.model_version,
            serverAttributeEnabled=active_settings.server_attribute_enabled,
            serverAttributeReady=attribute_readiness.server_attribute_ready,
            serverAttributeModel=attribute_readiness.model_version,
            serverAttributeReasons=attribute_readiness.reasons,
        )

    @app.post(
        "/v1/candidates/analyze",
        response_model=CandidateAnalysisResponse,
        responses={
            422: {"model": ErrorResponse},
            503: {"model": ErrorResponse},
            502: {"model": ErrorResponse},
        },
    )
    async def analyze(
        request: CandidateAnalysisRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> CandidateAnalysisResponse | JSONResponse:
        authorization_error = authorize_internal_request(active_settings, x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        try:
            image_path = validate_local_image(request.image_path, active_settings.image_root)
        except FileNotFoundError:
            logger.info("analysis image was not found", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    code="image_not_found", message="candidate image was not found"
                ).model_dump(),
            )
        except ValueError:
            logger.info("analysis image was invalid", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    code="invalid_image", message="candidate image is invalid"
                ).model_dump(),
            )
        request = request.model_copy(update={"image_path": str(image_path)})
        try:
            result = await run_inference(lambda: active_provider.analyze(request))
            return enforce_retrieval_only_analysis(result)
        except InferenceQueueTimeout:
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    code="inference_queue_timeout", message="inference queue is busy"
                ).model_dump(),
            )
        except ProviderUnavailable:
            logger.warning("analysis provider is unavailable", exc_info=True)
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    code="provider_unavailable", message="analysis provider is unavailable"
                ).model_dump(),
            )
        except ProviderInferenceError:
            logger.warning("analysis provider inference failed", exc_info=True)
            return JSONResponse(
                status_code=502,
                content=ErrorResponse(
                    code="provider_inference_failed",
                    message="analysis provider failed to produce a result",
                ).model_dump(),
            )

    @app.post("/v1/candidates/decide", response_model=DecisionResponse)
    async def decide(
        request: DecisionRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> DecisionResponse | JSONResponse:
        authorization_error = authorize_internal_request(active_settings, x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        return await to_thread.run_sync(decide_candidates, request)

    @app.post(
        "/v1/candidates/decide-with-qwen",
        response_model=DecisionResponse,
        responses={503: {"model": ErrorResponse}},
    )
    async def decide_with_qwen(
        request: QwenDecisionRequest,
        x_internal_api_key: str | None = Header(default=None, alias="X-Internal-API-Key"),
    ) -> DecisionResponse | JSONResponse:
        authorization_error = authorize_internal_request(active_settings, x_internal_api_key)
        if authorization_error is not None:
            return authorization_error
        try:
            return await run_inference(
                lambda: decide_with_qwen_candidates(request, active_provider, active_settings)
            )
        except InferenceQueueTimeout:
            return JSONResponse(
                status_code=503,
                content=ErrorResponse(
                    code="inference_queue_timeout", message="inference queue is busy"
                ).model_dump(),
            )
        except FileNotFoundError:
            logger.warning("decision image was not found", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    code="image_not_found", message="candidate image was not found"
                ).model_dump(),
            )
        except ValueError:
            logger.warning("decision evidence was invalid", exc_info=True)
            return JSONResponse(
                status_code=422,
                content=ErrorResponse(
                    code="invalid_decision_evidence", message="decision evidence is invalid"
                ).model_dump(),
            )
        except ProviderUnavailable:
            return review_on_provider_failure(
                request.case_id, request.priority, "qwen_provider_unavailable"
            )
        except ProviderInferenceError:
            return review_on_provider_failure(
                request.case_id, request.priority, "qwen_inference_failed"
            )

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    server_settings = get_settings()
    uvicorn.run(
        "qwen_backend.main:app",
        host=server_settings.server_host,
        port=server_settings.server_port,
        reload=False,
    )

