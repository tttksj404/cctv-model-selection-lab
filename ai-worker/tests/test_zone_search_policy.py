import pytest
from pydantic import ValidationError

from qwen_backend.zone_search_policy import (
    build_operator_decision_directive,
    build_zone_search_plan,
)
from qwen_backend.zone_search_schemas import (
    OperatorDecisionRequest,
    ZoneSearchPlanRequest,
)


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


def _plan_request(
    *,
    cameras: list[dict[str, int | float | str | bool]] | None = None,
    expected_zone_id: int | None = None,
    expected_zone_confidence: float = 0.0,
    live_search_enabled: bool = True,
) -> ZoneSearchPlanRequest:
    return ZoneSearchPlanRequest.model_validate(
        {
            "caseId": "case-77",
            "searchFrom": "2026-07-31T01:00:00Z",
            "searchTo": "2026-07-31T03:00:00Z",
            "zoneCount": 4,
            "camerasPerZone": 4,
            "expectedZoneId": expected_zone_id,
            "expectedZoneConfidence": expected_zone_confidence,
            "liveSearchEnabled": live_search_enabled,
            "cameras": cameras or _camera_payload(),
        }
    )


@pytest.mark.parametrize("zone_count", [3, 5])
def test_plan_contract_rejects_non_four_zone_jurisdiction(zone_count: int) -> None:
    payload = _plan_request().model_dump(mode="json", by_alias=True)
    payload["zoneCount"] = zone_count

    with pytest.raises(ValidationError):
        ZoneSearchPlanRequest.model_validate(payload)


def test_unavailable_representative_camera_falls_back_to_best_available() -> None:
    # Given
    cameras = _camera_payload()
    cameras[0]["available"] = False

    # When
    result = build_zone_search_plan(_plan_request(cameras=cameras))

    # Then
    selected_by_zone = {camera.zone_id: camera for camera in result.selected_cameras}
    assert selected_by_zone[1].camera_id == "1-2"


def test_zero_signal_zone_uses_deterministic_uniform_fallback() -> None:
    # Given
    cameras = _camera_payload()
    for camera in cameras[:4]:
        camera["recordingCoverage"] = 0.0
        camera["healthScore"] = 0.0
        camera["routeCentrality"] = 0.0
        camera["freshnessScore"] = 0.0
        camera["priorDetectionScore"] = 0.0
    cameras[0]["available"] = False

    # When
    result = build_zone_search_plan(_plan_request(cameras=cameras))

    # Then
    selected_by_zone = {camera.zone_id: camera for camera in result.selected_cameras}
    assert selected_by_zone[1].camera_id == "1-2"
    assert selected_by_zone[1].routing_weight == 0.333333


def test_expected_zone_changes_priority_without_excluding_other_zones() -> None:
    # Given
    request = _plan_request(expected_zone_id=3, expected_zone_confidence=0.9)

    # When
    result = build_zone_search_plan(request)

    # Then
    assert result.selected_cameras[0].zone_id == 3
    assert {camera.zone_id for camera in result.selected_cameras} == {1, 2, 3, 4}


def test_recordings_only_search_runs_oldest_first() -> None:
    # Given
    request = _plan_request(live_search_enabled=False)

    # When
    result = build_zone_search_plan(request)

    # Then
    assert result.segment_order == "oldest_first"


def test_confirmed_recording_candidate_does_not_activate_jetson() -> None:
    # Given
    request = OperatorDecisionRequest.model_validate(
        {
            "caseId": "case-77",
            "candidateId": "candidate-1",
            "candidateCameraId": "1-1",
            "candidateZoneId": 1,
            "decision": "confirmed_match",
            "decisionAt": "2026-07-31T03:05:00Z",
            "routingRevision": 1,
            "activeRoutingRevision": 0,
            "liveSearchEnabled": False,
            "zoneCameras": [
                {"cameraId": f"1-{position}", "zoneId": 1, "position": position}
                for position in range(1, 5)
            ],
            "modelSimilarity": 0.9,
            "calibratedMatchProbability": None,
        }
    )

    # When
    result = build_operator_decision_directive(request)

    # Then
    assert result.action == "record_historical_trace"
    assert result.target_zone_id is None
    assert result.replace_active_zone is False
    assert result.target_camera_ids == ()


def test_rejected_candidate_keeps_archive_search_without_jetson_command() -> None:
    # Given
    request = OperatorDecisionRequest.model_validate(
        {
            "caseId": "case-77",
            "candidateId": "candidate-1",
            "candidateCameraId": "1-1",
            "candidateZoneId": 1,
            "decision": "rejected",
            "decisionAt": "2026-07-31T03:05:00Z",
            "routingRevision": 1,
            "activeRoutingRevision": 0,
            "liveSearchEnabled": True,
            "zoneCameras": [
                {"cameraId": f"1-{position}", "zoneId": 1, "position": position}
                for position in range(1, 5)
            ],
            "modelSimilarity": 0.75,
            "calibratedMatchProbability": 0.4,
        }
    )

    # When
    result = build_operator_decision_directive(request)

    # Then
    assert result.action == "continue_archive_search"
    assert result.target_zone_id is None
    assert result.replace_active_zone is False
    assert result.target_camera_ids == ()

