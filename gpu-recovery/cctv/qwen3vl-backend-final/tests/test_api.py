from pathlib import Path

from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.main import create_app
from qwen_backend.providers import MockProvider, ProviderUnavailable
from qwen_backend.schemas import CandidateAnalysisRequest, CandidateAnalysisResponse


def test_health_does_not_load_model() -> None:
    app = create_app(Settings(provider="mock"))
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["modelLoaded"] is True


def test_analyze_happy_path(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock"))
    with TestClient(app) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "case_id": "case-1",
                "camera_id": "cam-1",
                "track_id": "track-1",
                "image_path": str(image),
                "search_condition": {"color": "red"},
            },
        )
    assert response.status_code == 200
    assert response.json()["decision"] == "match"


def test_analyze_missing_image_is_422(tmp_path: Path) -> None:
    app = create_app(Settings(provider="mock"))
    with TestClient(app) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "case_id": "case-1",
                "camera_id": "cam-1",
                "track_id": "track-1",
                "image_path": str(tmp_path / "missing.jpg"),
            },
        )
    assert response.status_code == 422


class FailingProvider(MockProvider):
    @property
    def model_loaded(self) -> bool:
        return False

    def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
        raise ProviderUnavailable("test provider unavailable")


def test_provider_failure_is_503(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="qwen"), provider=FailingProvider())
    with TestClient(app) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "case_id": "case-1",
                "camera_id": "cam-1",
                "track_id": "track-1",
                "image_path": str(image),
            },
        )
    assert response.status_code == 503
