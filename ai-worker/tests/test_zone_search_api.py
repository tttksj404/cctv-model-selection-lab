from auth_support import TEST_INTERNAL_HEADERS
from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.research_app import create_research_app as create_app


def _camera_payload() -> list[dict[str, int | float | str | bool]]:
    return [
        {
            "cameraId": f"{zone_id}-{position}",
            "zoneId": zone_id,
            "position": position,
            "available": True,
            "recordingCoverage": 1.0,
            "healthScore": 1.0,
            "routeCentrality": 0.7 if position == 1 else 0.5,
            "freshnessScore": 1.0,
            "priorDetectionScore": 0.0,
            "overlapPenalty": 0.0,
        }
        for zone_id in range(1, 5)
        for position in range(1, 5)
    ]


def test_plan_endpoint_selects_one_representative_per_zone() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/plan",
            json={
                "caseId": "case-77",
                "searchFrom": "2026-07-31T01:00:00Z",
                "searchTo": "2026-07-31T03:00:00Z",
                "zoneCount": 4,
                "camerasPerZone": 4,
                "expectedZoneId": None,
                "expectedZoneConfidence": 0.0,
                "liveSearchEnabled": True,
                "cameras": _camera_payload(),
            },
        )

    # Then
    assert response.status_code == 200
    payload = response.json()
    assert [item["cameraId"] for item in payload["selectedCameras"]] == [
        "1-1",
        "2-1",
        "3-1",
        "4-1",
    ]
    assert payload["analysisMode"] == "parallel_zone_representatives"
    assert payload["segmentOrder"] == "newest_first"
    assert payload["continueAfterCandidate"] is True


def test_operator_confirmation_activates_every_camera_in_candidate_zone() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/operator-decision",
            json={
                "caseId": "case-77",
                "candidateId": "candidate-4",
                "candidateCameraId": "4-1",
                "candidateZoneId": 4,
                "decision": "confirmed_match",
                "decisionAt": "2026-07-31T03:05:00Z",
                "routingRevision": 2,
                "activeRoutingRevision": 1,
                "liveSearchEnabled": True,
                "zoneCameras": [
                    {
                        "cameraId": f"4-{position}",
                        "zoneId": 4,
                        "position": position,
                    }
                    for position in range(1, 5)
                ],
                "modelSimilarity": 0.93,
                "calibratedMatchProbability": 0.88,
            },
        )

    # Then
    assert response.status_code == 200
    assert response.json() == {
        "schemaVersion": "eyesonu-zone-search-v1",
        "caseId": "case-77",
        "candidateId": "candidate-4",
        "action": "activate_candidate_zone",
        "decisionAt": "2026-07-31T03:05:00Z",
        "routingRevision": 2,
        "commandKey": "case-77:zone-routing:2",
        "targetZoneId": 4,
        "replaceActiveZone": True,
        "targetCameraIds": ["4-1", "4-2", "4-3", "4-4"],
        "continueRecordingAnalysis": True,
        "displayScore": 0.88,
        "scoreKind": "calibrated_match_probability",
    }


def test_candidate_event_returns_registration_directive_without_stopping_search() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/candidate-events",
            json={
                "caseId": "case-77",
                "candidateId": "candidate-1",
                "cameraId": "1-1",
                "zoneId": 1,
                "cameraPosition": 1,
                "zoneCameras": [
                    {"cameraId": f"1-{position}", "zoneId": 1, "position": position}
                    for position in range(1, 5)
                ],
                "modelSimilarity": 0.91,
                "calibratedMatchProbability": None,
            },
        )

    # Then
    assert response.status_code == 200
    assert response.json() == {
        "schemaVersion": "eyesonu-zone-search-v1",
        "caseId": "case-77",
        "candidateId": "candidate-1",
        "registrationAction": "register_immediately",
        "registrationCompleted": False,
        "eventKey": "case-77:candidate:candidate-1",
        "operatorReviewRequired": True,
        "continueRecordingAnalysis": True,
        "displayScore": 0.91,
        "scoreKind": "uncalibrated_similarity",
    }


def test_search_routing_endpoints_require_internal_api_key() -> None:
    # Given
    app = create_app(Settings(provider="mock", internal_api_key="internal-secret"))

    # When
    with TestClient(app) as client:
        response = client.post(
            "/v1/search-routing/plan",
            json={
                "caseId": "case-77",
                "searchFrom": "2026-07-31T01:00:00Z",
                "searchTo": "2026-07-31T03:00:00Z",
                "zoneCount": 4,
                "camerasPerZone": 4,
                "expectedZoneId": None,
                "expectedZoneConfidence": 0.0,
                "liveSearchEnabled": True,
                "cameras": _camera_payload(),
            },
        )

    # Then
    assert response.status_code == 401


def test_operator_decision_rejects_camera_from_another_zone() -> None:
    # Given
    app = create_app(Settings(provider="mock"))

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/operator-decision",
            json={
                "caseId": "case-77",
                "candidateId": "candidate-4",
                "candidateCameraId": "4-1",
                "candidateZoneId": 4,
                "decision": "confirmed_match",
                "decisionAt": "2026-07-31T03:05:00Z",
                "routingRevision": 2,
                "activeRoutingRevision": 1,
                "liveSearchEnabled": True,
                "zoneCameras": [
                    {"cameraId": "4-1", "zoneId": 4, "position": 1},
                    {"cameraId": "4-2", "zoneId": 4, "position": 2},
                    {"cameraId": "4-3", "zoneId": 4, "position": 3},
                    {"cameraId": "3-4", "zoneId": 3, "position": 4},
                ],
                "modelSimilarity": 0.93,
                "calibratedMatchProbability": 0.88,
            },
        )

    # Then
    assert response.status_code == 422


def test_plan_rejects_camera_outside_declared_topology() -> None:
    # Given
    app = create_app(Settings(provider="mock"))
    cameras = _camera_payload()
    cameras.append(
        {
            "cameraId": "5-1",
            "zoneId": 5,
            "position": 1,
            "available": True,
            "recordingCoverage": 1.0,
            "healthScore": 1.0,
            "routeCentrality": 0.5,
            "freshnessScore": 1.0,
            "priorDetectionScore": 0.0,
            "overlapPenalty": 0.0,
        }
    )

    # When
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/search-routing/plan",
            json={
                "caseId": "case-77",
                "searchFrom": "2026-07-31T01:00:00Z",
                "searchTo": "2026-07-31T03:00:00Z",
                "zoneCount": 4,
                "camerasPerZone": 4,
                "expectedZoneId": None,
                "expectedZoneConfidence": 0.0,
                "liveSearchEnabled": True,
                "cameras": cameras,
            },
        )

    # Then
    assert response.status_code == 422

