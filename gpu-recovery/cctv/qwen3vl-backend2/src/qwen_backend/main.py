from anyio import to_thread
from fastapi import FastAPI, HTTPException

from .config import Settings, get_settings
from .providers import (
    AnalysisProvider,
    MockProvider,
    ProviderInferenceError,
    ProviderUnavailable,
    Qwen3VLProvider,
)
from .schemas import (
    CandidateAnalysisRequest,
    CandidateAnalysisResponse,
    ErrorResponse,
    HealthResponse,
    validate_local_image,
)


def build_provider(settings: Settings) -> AnalysisProvider:
    if settings.provider == "mock":
        return MockProvider()
    return Qwen3VLProvider(settings)


def create_app(
    settings: Settings | None = None, provider: AnalysisProvider | None = None
) -> FastAPI:
    active_settings = settings or get_settings()
    active_provider = provider or build_provider(active_settings)
    app = FastAPI(title="Qwen3-VL Candidate Analyzer", version="0.1.0")

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok" if active_provider.model_loaded else "degraded",
            provider=active_settings.provider,
            modelLoaded=active_provider.model_loaded,
            modelVersion=active_provider.model_version,
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
    async def analyze(request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
        try:
            validate_local_image(request.image_path)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "image_not_found", "message": str(exc)}
            ) from exc
        except ValueError as exc:
            raise HTTPException(
                status_code=422, detail={"code": "invalid_image", "message": str(exc)}
            ) from exc
        try:
            return await to_thread.run_sync(active_provider.analyze, request)
        except ProviderUnavailable as exc:
            raise HTTPException(
                status_code=503, detail={"code": "provider_unavailable", "message": str(exc)}
            ) from exc
        except ProviderInferenceError as exc:
            raise HTTPException(
                status_code=502, detail={"code": "provider_inference_failed", "message": str(exc)}
            ) from exc

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("qwen_backend.main:app", host="127.0.0.1", port=8080, reload=False)
