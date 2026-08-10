from __future__ import annotations

from collections import defaultdict
from typing import Final

from .zone_search_schemas import (
    AnalysisMode,
    CameraRoutingInput,
    CandidateEventDirective,
    CandidateEventRequest,
    CandidateRegistrationAction,
    JetsonAction,
    OperatorDecision,
    OperatorDecisionDirective,
    OperatorDecisionRequest,
    RoutingScoreBreakdown,
    ScoreKind,
    SegmentOrder,
    SelectedCamera,
    ZoneSearchPlanRequest,
    ZoneSearchPlanResponse,
)

RECORDING_WEIGHT: Final = 0.30
HEALTH_WEIGHT: Final = 0.25
CENTRALITY_WEIGHT: Final = 0.20
FRESHNESS_WEIGHT: Final = 0.10
DETECTION_WEIGHT: Final = 0.10
REPRESENTATIVE_BONUS: Final = 0.05
OVERLAP_WEIGHT: Final = 0.10
NON_CONFIRMING_ACTIONS: Final[dict[OperatorDecision, JetsonAction]] = {
    OperatorDecision.REJECTED: JetsonAction.CONTINUE_ARCHIVE_SEARCH,
    OperatorDecision.REVIEW_REQUIRED: JetsonAction.AWAIT_OPERATOR_CONFIRMATION,
}


def _score_camera(
    camera: CameraRoutingInput,
) -> tuple[float, RoutingScoreBreakdown]:
    breakdown = RoutingScoreBreakdown(
        recording_coverage=RECORDING_WEIGHT * camera.recording_coverage,
        health=HEALTH_WEIGHT * camera.health_score,
        route_centrality=CENTRALITY_WEIGHT * camera.route_centrality,
        freshness=FRESHNESS_WEIGHT * camera.freshness_score,
        prior_detection=DETECTION_WEIGHT * camera.prior_detection_score,
        representative_bonus=(
            REPRESENTATIVE_BONUS if camera.position == 1 else 0.0
        ),
        overlap_penalty=-(OVERLAP_WEIGHT * camera.overlap_penalty),
    )
    score = (
        breakdown.recording_coverage
        + breakdown.health
        + breakdown.route_centrality
        + breakdown.freshness
        + breakdown.prior_detection
        + breakdown.representative_bonus
        + breakdown.overlap_penalty
    )
    return max(0.0, min(1.0, score)), breakdown


def _expected_zone_prior(request: ZoneSearchPlanRequest, zone_id: int) -> float:
    if request.expected_zone_id is None:
        return 1.0 / request.zone_count
    if zone_id == request.expected_zone_id:
        return request.expected_zone_confidence
    if request.zone_count == 1:
        return 0.0
    return (1.0 - request.expected_zone_confidence) / (request.zone_count - 1)


def _zone_priority(
    request: ZoneSearchPlanRequest,
    zone_id: int,
    cameras: tuple[CameraRoutingInput, ...],
) -> float:
    prior = _expected_zone_prior(request, zone_id)
    activity = max(camera.prior_detection_score for camera in cameras)
    coverage = sum(camera.recording_coverage for camera in cameras) / len(cameras)
    priority = (0.70 * prior) + (0.20 * activity) + (0.10 * coverage)
    return max(0.0, min(1.0, priority))


def build_zone_search_plan(request: ZoneSearchPlanRequest) -> ZoneSearchPlanResponse:
    cameras_by_zone: defaultdict[int, list[CameraRoutingInput]] = defaultdict(list)
    for camera in request.cameras:
        cameras_by_zone[camera.zone_id].append(camera)

    selected: list[SelectedCamera] = []
    for zone_id in range(1, request.zone_count + 1):
        zone_cameras = tuple(cameras_by_zone[zone_id])
        scored = [
            (camera, *_score_camera(camera))
            for camera in zone_cameras
            if camera.available
        ]
        score_sum = sum(score for _, score, _ in scored)
        camera, score, breakdown = sorted(
            scored,
            key=lambda item: (-item[1], item[0].position, item[0].camera_id),
        )[0]
        routing_weight = (
            score / score_sum if score_sum > 0.0 else 1.0 / len(scored)
        )
        selected.append(
            SelectedCamera(
                camera_id=camera.camera_id,
                zone_id=zone_id,
                position=camera.position,
                selection_score=round(score, 6),
                routing_weight=round(routing_weight, 6),
                zone_priority=round(_zone_priority(request, zone_id, zone_cameras), 6),
                score_breakdown=breakdown,
            )
        )

    selected.sort(key=lambda item: (-item.zone_priority, item.zone_id))
    segment_order = (
        SegmentOrder.NEWEST_FIRST
        if request.live_search_enabled
        else SegmentOrder.OLDEST_FIRST
    )
    return ZoneSearchPlanResponse(
        case_id=request.case_id,
        analysis_mode=AnalysisMode.PARALLEL_ZONE_REPRESENTATIVES,
        segment_order=segment_order,
        selected_cameras=tuple(selected),
    )


def _display_score(
    model_similarity: float,
    calibrated_match_probability: float | None,
) -> tuple[float, ScoreKind]:
    if calibrated_match_probability is None:
        return model_similarity, ScoreKind.UNCALIBRATED_SIMILARITY
    return calibrated_match_probability, ScoreKind.CALIBRATED_MATCH_PROBABILITY


def build_candidate_event_directive(
    request: CandidateEventRequest,
) -> CandidateEventDirective:
    display_score, score_kind = _display_score(
        request.model_similarity,
        request.calibrated_match_probability,
    )
    return CandidateEventDirective(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        registration_action=CandidateRegistrationAction.REGISTER_IMMEDIATELY,
        event_key=f"{request.case_id}:candidate:{request.candidate_id}",
        display_score=display_score,
        score_kind=score_kind,
    )


def build_operator_decision_directive(
    request: OperatorDecisionRequest,
) -> OperatorDecisionDirective:
    display_score, score_kind = _display_score(
        request.model_similarity,
        request.calibrated_match_probability,
    )
    if request.routing_revision <= request.active_routing_revision:
        action = JetsonAction.IGNORE_STALE_DECISION
        target_zone_id = None
        replace_active_zone = False
        target_camera_ids = ()
    elif request.decision is OperatorDecision.CONFIRMED_MATCH:
        if request.live_search_enabled:
            action = JetsonAction.ACTIVATE_CANDIDATE_ZONE
            target_zone_id = request.candidate_zone_id
            replace_active_zone = True
            target_camera_ids = tuple(
                camera.camera_id
                for camera in sorted(
                    request.zone_cameras,
                    key=lambda camera: camera.position,
                )
            )
        else:
            action = JetsonAction.RECORD_HISTORICAL_TRACE
            target_zone_id = None
            replace_active_zone = False
            target_camera_ids = ()
    else:
        action = NON_CONFIRMING_ACTIONS[request.decision]
        target_zone_id = None
        replace_active_zone = False
        target_camera_ids = ()
    return OperatorDecisionDirective(
        case_id=request.case_id,
        candidate_id=request.candidate_id,
        action=action,
        decision_at=request.decision_at,
        routing_revision=request.routing_revision,
        command_key=f"{request.case_id}:zone-routing:{request.routing_revision}",
        target_zone_id=target_zone_id,
        replace_active_zone=replace_active_zone,
        target_camera_ids=target_camera_ids,
        display_score=display_score,
        score_kind=score_kind,
    )

