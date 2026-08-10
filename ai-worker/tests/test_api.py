import time
from pathlib import Path

import pytest
from auth_support import TEST_INTERNAL_HEADERS
from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.main import create_app
from qwen_backend.providers import MockProvider, ProviderInferenceError, ProviderUnavailable
from qwen_backend.schemas import (
    CandidateAnalysisRequest,
    CandidateAnalysisResponse,
    CandidateAttributes,
)


def test_health_does_not_load_model() -> None:
    app = create_app(Settings(provider="mock"))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert response.json()["modelLoaded"] is False


def test_analyze_happy_path(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
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
    assert response.json()["decision"] == "review"
    assert response.json()["semanticMatchScore"] == 0.5


def test_analyze_downgrades_provider_match_to_review(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")

    class MatchProvider(MockProvider):
        def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
            return CandidateAnalysisResponse(
                case_id=request.case_id,
                camera_id=request.camera_id,
                track_id=request.track_id,
                decision="match",
                attributes=CandidateAttributes(color="red"),
                confidence=0.99,
                semanticMatchScore=0.99,
                modelVersion="match-provider-test",
                latencyMs=1.0,
                failureReason=None,
            )

    app = create_app(
        Settings(provider="mock", image_root=tmp_path),
        provider=MatchProvider(),
    )
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "caseId": "case-gated",
                "cameraId": "cam-1",
                "trackId": "track-1",
                "imagePath": str(image),
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
    assert response.json()["failureReason"] == "automatic_match_disabled"


def test_analyze_score_can_feed_case_decision(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        analysis = client.post(
            "/v1/candidates/analyze",
            json={
                "caseId": "case-1",
                "cameraId": "cam-1",
                "trackId": "track-1",
                "imagePath": str(image),
                "searchCondition": {"color": "red"},
            },
        )
        decision = client.post(
            "/v1/candidates/decide",
            json={
                "caseId": "case-1",
                "candidates": [
                    {
                        "candidateId": "track-1",
                        "trackId": "track-1",
                        "cameraId": "cam-1",
                        "embeddedClipScore": 0.94,
                        "historicalRetrievalScore": 0.91,
                        "qwenSemanticScore": analysis.json()["semanticMatchScore"],
                        "qwenConfidence": analysis.json()["confidence"],
                        "trackConsistency": 0.90,
                        "temporalConsistency": 0.90,
                        "spatialConsistency": 0.90,
                        "imageQuality": 0.90,
                        "observedFrames": 8,
                    }
                ],
            },
        )

    assert analysis.status_code == 200
    assert decision.status_code == 200
    assert decision.json()["decision"] == "review"


def test_decide_with_qwen_runs_provider_and_case_decision(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/decide-with-qwen",
            json={
                "caseId": "case-1",
                "candidates": [
                    {
                        "candidateId": "track-1",
                        "trackId": "track-1",
                        "cameraId": "cam-1",
                        "imagePath": str(image),
                        "searchCondition": {"color": "red"},
                        "embeddedClipScore": 0.94,
                        "historicalRetrievalScore": 0.91,
                        "trackConsistency": 0.90,
                        "temporalConsistency": 0.90,
                        "spatialConsistency": 0.90,
                        "imageQuality": 0.90,
                        "observedFrames": 8,
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
    assert response.json()["selectedCandidateId"] is None


def test_production_cannot_start_with_mock_provider() -> None:
    with pytest.raises(RuntimeError, match="mock provider is disabled in production"):
        create_app(Settings(provider="mock", environment="production"))


def test_decide_with_qwen_fails_closed_when_provider_fails(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")

    class FailingProvider(MockProvider):
        def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
            raise ProviderInferenceError("simulated failure")

    app = create_app(Settings(provider="mock", image_root=tmp_path), provider=FailingProvider())
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/decide-with-qwen",
            json={
                "caseId": "case-1",
                "priority": "critical",
                "candidates": [
                    {
                        "candidateId": "track-1",
                        "trackId": "track-1",
                        "cameraId": "cam-1",
                        "imagePath": str(image),
                    }
                ],
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
    assert response.json()["escalation"] == "urgent_operator_review"
    assert response.json()["reasons"] == ["qwen_inference_failed"]


def test_decision_endpoint_requires_internal_key_when_configured() -> None:
    app = create_app(Settings(provider="mock", internal_api_key="secret"))
    with TestClient(app) as client:
        missing = client.post(
            "/v1/candidates/decide",
            json={"caseId": "case-1", "candidates": []},
        )
        invalid = client.post(
            "/v1/candidates/decide",
            headers={"X-Internal-API-Key": "wrong"},
            json={"caseId": "case-1", "candidates": []},
        )
        valid = client.post(
            "/v1/candidates/decide",
            headers={"X-Internal-API-Key": "secret"},
            json={"caseId": "case-1", "candidates": []},
        )

    assert missing.status_code == 401
    assert invalid.status_code == 401
    assert valid.status_code == 200


def test_mock_provider_rejects_missing_internal_key_configuration() -> None:
    app = create_app(Settings(provider="mock", internal_api_key=None))
    with TestClient(app) as client:
        response = client.post(
            "/v1/candidates/decide",
            json={"caseId": "case-1", "candidates": []},
        )

    assert response.status_code == 503
    assert response.json()["code"] == "service_misconfigured"


def test_qwen_provider_rejects_missing_internal_key() -> None:
    app = create_app(Settings(provider="qwen", internal_api_key=None))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/decide",
            json={"caseId": "case-1", "candidates": []},
        )

    assert response.status_code == 503
    assert response.json()["code"] == "service_misconfigured"


def test_inference_queue_timeout_returns_503(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")

    class SlowProvider(MockProvider):
        def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
            time.sleep(0.05)
            return super().analyze(request)

    app = create_app(
        Settings(
            provider="mock",
            image_root=tmp_path,
            inference_queue_timeout_ms=1,
        ),
        provider=SlowProvider(),
    )
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "caseId": "case-1",
                "cameraId": "cam-1",
                "trackId": "track-1",
                "imagePath": str(image),
            },
        )

    assert response.status_code == 503
    assert response.json()["code"] == "inference_queue_timeout"


def test_analyze_accepts_camel_case_contract(tmp_path: Path) -> None:
    image = tmp_path / "candidate.png"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "caseId": "case-1",
                "cameraId": "cam-1",
                "trackId": "track-1",
                "imagePath": str(image),
                "searchCondition": {"objectName": "person"},
            },
        )
    assert response.status_code == 200
    assert response.json()["attributes"]["objectName"] == "person"


def test_analyze_missing_image_is_422(tmp_path: Path) -> None:
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
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
    assert response.json()["code"] == "image_not_found"


def test_analyze_rejects_image_outside_root(tmp_path: Path) -> None:
    image = tmp_path.parent / "outside.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="mock", image_root=tmp_path))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/analyze",
            json={
                "case_id": "case-1",
                "camera_id": "cam-1",
                "track_id": "track-1",
                "image_path": str(image),
            },
        )
    image.unlink()
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_image"


class FailingProvider(MockProvider):
    @property
    def model_loaded(self) -> bool:
        return False

    def analyze(self, request: CandidateAnalysisRequest) -> CandidateAnalysisResponse:
        raise ProviderUnavailable("test provider unavailable")


def test_provider_failure_is_503(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    app = create_app(Settings(provider="qwen", image_root=tmp_path), provider=FailingProvider())
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
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
    assert str(tmp_path) not in response.json()["message"]

