from auth_support import TEST_INTERNAL_HEADERS
from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.research_app import create_research_app as create_app


def _zone_cameras(zone_id: int) -> list[dict[str, int | str]]:
    return [
        {
            "cameraId": f"{zone_id}-{position}",
            "zoneId": zone_id,
            "position": position,
        }
        for position in range(1, 5)
    ]


def test_candidate_event_rejects_camera_zone_mismatch() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/candidate-events",
            json={
                "caseId": "case-77",
                "candidateId": "candidate-4",
                "cameraId": "4-1",
                "zoneId": 1,
                "cameraPosition": 1,
                "zoneCameras": _zone_cameras(4),
                "modelSimilarity": 0.91,
                "calibratedMatchProbability": None,
            },
        )

    # Then
    assert response.status_code == 422


def test_stale_zone_decision_never_reactivates_previous_zone() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/operator-decision",
            json={
                "caseId": "case-77",
                "candidateId": "candidate-1",
                "candidateCameraId": "1-1",
                "candidateZoneId": 1,
                "decision": "confirmed_match",
                "decisionAt": "2026-07-31T03:04:00Z",
                "routingRevision": 1,
                "activeRoutingRevision": 2,
                "liveSearchEnabled": True,
                "zoneCameras": _zone_cameras(1),
                "modelSimilarity": 0.93,
                "calibratedMatchProbability": 0.88,
            },
        )

    # Then
    assert response.status_code == 200
    payload = response.json()
    assert payload["action"] == "ignore_stale_decision"
    assert payload["routingRevision"] == 1
    assert payload["commandKey"] == "case-77:zone-routing:1"
    assert payload["replaceActiveZone"] is False
    assert payload["targetCameraIds"] == []

