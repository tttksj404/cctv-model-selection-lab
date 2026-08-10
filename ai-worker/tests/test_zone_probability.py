from __future__ import annotations

import pytest
from pydantic import ValidationError
from zone_probability_support import cameras as _cameras
from zone_probability_support import evidence as _evidence
from zone_probability_support import request as _support_request

from qwen_backend.zone_probability import assess_zone_probability
from qwen_backend.zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateProbabilityEvidence,
    ZoneBeliefInput,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
)


def _request(
    *,
    evidence: tuple[CandidateProbabilityEvidence, ...] = (),
    cameras: tuple[CameraObservation, ...] | None = None,
) -> ZoneProbabilityRequest:
    return _support_request(evidence_items=evidence, camera_items=cameras)


@pytest.mark.parametrize("zone_count", [3, 5])
def test_probability_contract_rejects_non_four_zone_jurisdiction(zone_count: int) -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["zoneCount"] = zone_count

    with pytest.raises(ValidationError):
        ZoneProbabilityRequest.model_validate(payload)


def test_strong_track_evidence_moves_posterior_to_observed_zone() -> None:
    result = assess_zone_probability(_request(evidence=(_evidence(),)))

    posterior = {item.zone_id: item.probability for item in result.zone_posterior}
    assert posterior[3] > 0.50
    assert result.candidate_assessments[0].priority_band == "high_priority"
    assert result.operator_review_required is True
    assert result.auto_match_allowed is False


def test_duplicate_frames_from_same_track_do_not_multiply_confidence() -> None:
    single = assess_zone_probability(_request(evidence=(_evidence(),)))
    duplicate = assess_zone_probability(
        _request(
            evidence=(
                _evidence(event_id="event-1"),
                _evidence(event_id="event-2", quality=0.8),
            )
        )
    )

    assert duplicate.zone_posterior == single.zone_posterior
    assert duplicate.suppressed_correlated_event_ids == ("event-2",)


def test_same_physical_track_is_not_reapplied_across_continuation_windows() -> None:
    first = assess_zone_probability(_request(evidence=(_evidence(event_id="window-1"),)))
    continuation = ZoneProbabilityRequest(
        case_id="case-77",
        routing_revision=4,
        active_routing_revision=first.routing_revision,
        zone_count=4,
        candidate_prior_probability=0.10,
        advance_motion=False,
        previous_zone_posterior=tuple(
            ZoneBeliefInput(zone_id=item.zone_id, probability=item.probability)
            for item in first.zone_posterior
        ),
        previous_outside_probability=first.outside_probability,
        previous_unknown_probability=first.unknown_probability,
        previous_deduplication_state=first.deduplication_state,
        evidence=(
            _evidence(
                event_id="window-2",
                observation_group_id="recording-31:camera-3-1:segment-2",
            ),
        ),
        cameras=_cameras(),
    )

    second = assess_zone_probability(continuation)

    assert second.zone_posterior == first.zone_posterior
    assert second.outside_probability == first.outside_probability
    assert second.unknown_probability == first.unknown_probability
    assert second.suppressed_correlated_event_ids == ("window-2",)
    assert second.candidate_assessments == ()


def test_continuation_revision_requires_signed_deduplication_state() -> None:
    first = assess_zone_probability(_request())
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["routingRevision"] = 4
    payload["activeRoutingRevision"] = first.routing_revision
    payload["previousZonePosterior"] = [
        item.model_dump(mode="json", by_alias=True) for item in first.zone_posterior
    ]
    payload["previousOutsideProbability"] = first.outside_probability
    payload["previousUnknownProbability"] = first.unknown_probability

    with pytest.raises(ValidationError, match="previousDeduplicationState"):
        ZoneProbabilityRequest.model_validate(payload)


def test_same_local_track_id_from_different_cameras_is_not_suppressed() -> None:
    first = _evidence(
        event_id="event-1",
        track_id="track-1",
        correlation_group_id="camera-1-local-track-1",
        zone_id=1,
    )
    second = _evidence(
        event_id="event-2",
        track_id="track-1",
        correlation_group_id="camera-2-local-track-1",
        zone_id=2,
    )

    result = assess_zone_probability(_request(evidence=(first, second)))

    assert len(result.candidate_assessments) == 2
    assert result.suppressed_correlated_event_ids == ()


def test_same_physical_track_across_cameras_is_counted_once() -> None:
    first = _evidence(event_id="event-1", zone_id=1, quality=1.0)
    second = _evidence(event_id="event-2", zone_id=2, quality=0.8)

    single = assess_zone_probability(_request(evidence=(first,)))
    result = assess_zone_probability(_request(evidence=(first, second)))

    assert result.zone_posterior == single.zone_posterior
    assert result.suppressed_correlated_event_ids == ("event-2",)


def test_track_quality_is_applied_once_when_selecting_correlated_evidence() -> None:
    stronger = _evidence(
        event_id="stronger-once-weighted",
        probability=0.92,
        quality=0.5,
    )
    weaker = _evidence(
        event_id="weaker-if-quality-is-squared",
        probability=0.5,
        quality=0.8,
    )

    expected = assess_zone_probability(_request(evidence=(stronger,)))
    result = assess_zone_probability(_request(evidence=(stronger, weaker)))

    assert result.zone_posterior == expected.zone_posterior
    assert result.suppressed_correlated_event_ids == ("weaker-if-quality-is-squared",)


def test_reliable_no_match_observation_reduces_zone_probability() -> None:
    baseline = assess_zone_probability(_request())
    no_match = assess_zone_probability(
        _request(cameras=_cameras(zone_one_observation=CameraObservationStatus.NO_MATCH))
    )

    baseline_zone_one = baseline.zone_posterior[0].probability
    no_match_zone_one = no_match.zone_posterior[0].probability
    assert no_match_zone_one < baseline_zone_one


def test_expected_information_gain_prefers_camera_in_most_likely_zone() -> None:
    result = assess_zone_probability(_request(evidence=(_evidence(zone_id=4),)))

    assert result.ranked_cameras[0].zone_id == 4
    assert result.ranked_cameras[0].expected_information_gain > 0.0
    assert result.next_camera_id == result.ranked_cameras[0].camera_id
    assert result.camera_selection_policy == "posterior_weighted_coverage_with_eig_tiebreak"


def test_posterior_including_outside_and_unknown_is_normalized() -> None:
    result = assess_zone_probability(_request(evidence=(_evidence(probability=0.73),)))

    total = (
        sum(item.probability for item in result.zone_posterior)
        + result.outside_probability
        + result.unknown_probability
    )
    assert abs(total - 1.0) < 1e-9


def test_duplicate_previous_zone_ids_are_rejected_before_dict_conversion() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["previousZonePosterior"] = [
        {"zoneId": 1, "probability": 0.05},
        {"zoneId": 1, "probability": 0.05},
        {"zoneId": 2, "probability": 0.10},
        {"zoneId": 3, "probability": 0.10},
        {"zoneId": 4, "probability": 0.10},
    ]
    payload["previousOutsideProbability"] = 0.30
    payload["previousUnknownProbability"] = 0.30

    with pytest.raises(ValidationError, match="every zone exactly once"):
        ZoneProbabilityRequest.model_validate(payload)


def test_outside_and_unknown_priors_cannot_exceed_total_probability() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["previousOutsideProbability"] = 0.80
    payload["previousUnknownProbability"] = 0.80

    with pytest.raises(ValidationError, match="leave positive probability for zones"):
        ZoneProbabilityRequest.model_validate(payload)


def test_elapsed_time_changes_motion_prediction() -> None:
    previous = tuple(
        ZoneBeliefInput(zone_id=zone_id, probability=0.70 if zone_id == 1 else 0.05)
        for zone_id in range(1, 5)
    )
    common = _request().model_copy(
        update={
            "previous_zone_posterior": previous,
            "previous_outside_probability": 0.10,
            "previous_unknown_probability": 0.05,
            "motion_step_seconds": 300,
        }
    )
    one_second = common.model_copy(update={"motion_elapsed_seconds": 1})
    one_hour = common.model_copy(update={"motion_elapsed_seconds": 3_600})

    short_result = assess_zone_probability(one_second)
    long_result = assess_zone_probability(one_hour)

    assert short_result.zone_posterior[0].probability > long_result.zone_posterior[0].probability


def test_stale_probability_revision_is_rejected() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["routingRevision"] = 2
    payload["activeRoutingRevision"] = 2

    with pytest.raises(ValidationError, match="newer than activeRoutingRevision"):
        ZoneProbabilityRequest.model_validate(payload)


def test_probability_equal_to_calibration_base_rate_adds_no_zone_evidence() -> None:
    baseline = assess_zone_probability(_request())
    neutral = assess_zone_probability(_request(evidence=(_evidence(probability=0.10),)))

    assert neutral.zone_posterior == baseline.zone_posterior


def test_candidate_pool_is_ranked_and_exposes_zone_presence_probability() -> None:
    weak = _evidence(
        event_id="weak-zone-1",
        track_id="track-weak",
        correlation_group_id="physical-track-weak",
        zone_id=1,
        probability=0.35,
    )
    strong = _evidence(
        event_id="strong-zone-4",
        track_id="track-strong",
        correlation_group_id="physical-track-strong",
        zone_id=4,
        probability=0.92,
    )

    result = assess_zone_probability(_request(evidence=(weak, strong)))

    assert tuple(item.event_id for item in result.candidate_assessments) == (
        "strong-zone-4",
        "weak-zone-1",
    )
    assert result.most_likely_zone_id == 4
    assert result.most_likely_zone_probability == result.zone_posterior[3].probability
    assert result.candidate_pool_status == "candidate_found"
    zone_four = next(item for item in result.zone_candidate_summaries if item.zone_id == 4)
    assert zone_four.candidate_count == 1
    assert zone_four.top_candidate_event_id == "strong-zone-4"
    assert zone_four.zone_presence_probability == result.most_likely_zone_probability


def test_competing_top_k_candidates_from_one_segment_do_not_multiply_zone_probability() -> None:
    strongest = _evidence(
        event_id="segment-candidate-1",
        track_id="track-1",
        correlation_group_id="physical-track-1",
        observation_group_id="recording-31:camera-3-1:segment-7",
        probability=0.92,
    )
    alternative = _evidence(
        event_id="segment-candidate-2",
        track_id="track-2",
        correlation_group_id="physical-track-2",
        observation_group_id="recording-31:camera-3-1:segment-7",
        probability=0.80,
    )

    single = assess_zone_probability(_request(evidence=(strongest,)))
    candidate_pool = assess_zone_probability(_request(evidence=(strongest, alternative)))

    assert candidate_pool.zone_posterior == single.zone_posterior
    assert len(candidate_pool.candidate_assessments) == 2
    assert candidate_pool.suppressed_alternative_event_ids == ("segment-candidate-2",)
    used = {
        item.event_id: item.used_for_zone_update
        for item in candidate_pool.candidate_assessments
    }
    assert used == {"segment-candidate-1": True, "segment-candidate-2": False}


def test_same_camera_track_cannot_change_correlation_group_between_segments() -> None:
    first = _evidence(
        event_id="segment-1-track-7",
        track_id="recording-31:track-7",
        correlation_group_id="physical-track-a",
        observation_group_id="recording-31:camera-3-1:segment-1",
    )
    conflicting = _evidence(
        event_id="segment-2-track-7",
        track_id="recording-31:track-7",
        correlation_group_id="physical-track-b",
        observation_group_id="recording-31:camera-3-1:segment-2",
    )

    with pytest.raises(ValidationError, match="same cameraId and trackId"):
        _request(evidence=(first, conflicting))


def test_excessive_motion_transition_steps_are_rejected() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["motionElapsedSeconds"] = 1_001
    payload["motionStepSeconds"] = 1

    with pytest.raises(ValidationError, match="motion transition steps"):
        ZoneProbabilityRequest.model_validate(payload)


def test_duplicate_event_ids_are_rejected() -> None:
    duplicate_id = (
        _evidence(
            event_id="duplicate-event",
            track_id="recording-31:track-1",
            correlation_group_id="physical-track-1",
            observation_group_id="recording-31:camera-3-1:segment-1",
        ),
        _evidence(
            event_id="duplicate-event",
            track_id="recording-31:track-2",
            correlation_group_id="physical-track-2",
            observation_group_id="recording-31:camera-3-1:segment-2",
        ),
    )

    with pytest.raises(ValidationError, match="eventId values must be unique"):
        _request(evidence=duplicate_id)


def test_topology_edges_have_a_bounded_request_size() -> None:
    payload = _request().model_dump(mode="json", by_alias=True)
    payload["topologyEdges"] = [
        {"sourceZoneId": 1, "targetZoneId": 2} for _ in range(401)
    ]

    with pytest.raises(ValidationError):
        ZoneProbabilityRequest.model_validate(payload)


def test_probability_response_cannot_enable_automatic_match() -> None:
    payload = assess_zone_probability(_request()).model_dump(mode="json", by_alias=True)
    payload["operatorReviewRequired"] = False
    payload["autoMatchAllowed"] = True

    with pytest.raises(ValidationError, match="operator review must remain required"):
        ZoneProbabilityResponse.model_validate(payload)

