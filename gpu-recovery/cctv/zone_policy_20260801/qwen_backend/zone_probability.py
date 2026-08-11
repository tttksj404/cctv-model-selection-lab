from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Final, Literal, TypeAlias

from .zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateAssessment,
    CandidatePriorityBand,
    CandidateProbabilityEvidence,
    RankedCamera,
    ZonePosteriorItem,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
)

ZoneState: TypeAlias = int | Literal["outside", "unknown"]
OUTSIDE: Final[Literal["outside"]] = "outside"
UNKNOWN: Final[Literal["unknown"]] = "unknown"
EPSILON: Final = 1e-9
MAX_LIKELIHOOD_RATIO: Final = 1_000.0
HIGH_PRIORITY_THRESHOLD: Final = 0.85
LOW_PRIORITY_THRESHOLD: Final = 0.15


def _odds(probability: float) -> float:
    bounded = min(1.0 - EPSILON, max(EPSILON, probability))
    return bounded / (1.0 - bounded)


def _event_log_likelihood_ratio(evidence: CandidateProbabilityEvidence) -> float:
    weighted_sum = 0.0
    weight_sum = 0.0
    for signal in evidence.signals:
        signal_lr = _odds(signal.probability) / _odds(signal.calibration_base_rate)
        weighted_sum += signal.reliability * math.log(signal_lr)
        weight_sum += signal.reliability
    return evidence.track_quality * weighted_sum / weight_sum


def _event_likelihood_ratio(evidence: CandidateProbabilityEvidence) -> float:
    raw = math.exp(_event_log_likelihood_ratio(evidence))
    return min(MAX_LIKELIHOOD_RATIO, max(1.0 / MAX_LIKELIHOOD_RATIO, raw))


def _candidate_probability(prior: float, likelihood_ratio: float) -> float:
    posterior_odds = _odds(prior) * likelihood_ratio
    return posterior_odds / (1.0 + posterior_odds)


def _priority_band(probability: float) -> CandidatePriorityBand:
    if probability >= HIGH_PRIORITY_THRESHOLD:
        return CandidatePriorityBand.HIGH_PRIORITY
    if probability <= LOW_PRIORITY_THRESHOLD:
        return CandidatePriorityBand.LOW_PRIORITY
    return CandidatePriorityBand.REVIEW


def _deduplicate_tracks(
    evidence: tuple[CandidateProbabilityEvidence, ...],
) -> tuple[tuple[CandidateProbabilityEvidence, ...], tuple[str, ...]]:
    grouped: defaultdict[str, list[CandidateProbabilityEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.track_id].append(item)
    selected: list[CandidateProbabilityEvidence] = []
    suppressed: list[str] = []
    for track_id in sorted(grouped):
        ranked = sorted(
            grouped[track_id],
            key=lambda item: (
                -(item.track_quality * abs(_event_log_likelihood_ratio(item))),
                item.event_id,
            ),
        )
        selected.append(ranked[0])
        suppressed.extend(item.event_id for item in ranked[1:])
    return tuple(selected), tuple(sorted(suppressed))


def _initial_belief(request: ZoneProbabilityRequest) -> dict[ZoneState, float]:
    if request.previous_zone_posterior:
        belief: dict[ZoneState, float] = {
            item.zone_id: item.probability for item in request.previous_zone_posterior
        }
    else:
        remaining = 1.0 - (
            request.previous_outside_probability + request.previous_unknown_probability
        )
        belief = {
            zone_id: remaining / request.zone_count
            for zone_id in range(1, request.zone_count + 1)
        }
    belief[OUTSIDE] = request.previous_outside_probability
    belief[UNKNOWN] = request.previous_unknown_probability
    return belief


def _adjacency(request: ZoneProbabilityRequest) -> dict[int, tuple[int, ...]]:
    neighbors: defaultdict[int, set[int]] = defaultdict(set)
    if request.topology_edges:
        for edge in request.topology_edges:
            neighbors[edge.source_zone_id].add(edge.target_zone_id)
            neighbors[edge.target_zone_id].add(edge.source_zone_id)
    elif request.zone_count == 4:
        for left, right in ((1, 2), (1, 3), (2, 4), (3, 4)):
            neighbors[left].add(right)
            neighbors[right].add(left)
    else:
        for zone_id in range(1, request.zone_count + 1):
            if zone_id > 1:
                neighbors[zone_id].add(zone_id - 1)
            if zone_id < request.zone_count:
                neighbors[zone_id].add(zone_id + 1)
    return {
        zone_id: tuple(sorted(neighbors[zone_id]))
        for zone_id in range(1, request.zone_count + 1)
    }


def _predict_motion(
    belief: Mapping[ZoneState, float],
    request: ZoneProbabilityRequest,
) -> dict[ZoneState, float]:
    predicted: dict[ZoneState, float] = {
        state: 0.0
        for state in (*range(1, request.zone_count + 1), OUTSIDE, UNKNOWN)
    }
    neighbors = _adjacency(request)
    for zone_id in range(1, request.zone_count + 1):
        mass = belief[zone_id]
        predicted[zone_id] += 0.70 * mass
        adjacent = neighbors[zone_id]
        if adjacent:
            share = 0.20 * mass / len(adjacent)
            for target in adjacent:
                predicted[target] += share
        else:
            predicted[zone_id] += 0.20 * mass
        predicted[OUTSIDE] += 0.05 * mass
        predicted[UNKNOWN] += 0.05 * mass
    outside_mass = belief[OUTSIDE]
    predicted[OUTSIDE] += 0.80 * outside_mass
    predicted[UNKNOWN] += 0.05 * outside_mass
    for zone_id in range(1, request.zone_count + 1):
        predicted[zone_id] += 0.15 * outside_mass / request.zone_count
    unknown_mass = belief[UNKNOWN]
    predicted[UNKNOWN] += 0.60 * unknown_mass
    predicted[OUTSIDE] += 0.10 * unknown_mass
    for zone_id in range(1, request.zone_count + 1):
        predicted[zone_id] += 0.30 * unknown_mass / request.zone_count
    return predicted


def _detection_probability(camera: CameraObservation, state: ZoneState) -> float:
    operational = camera.recording_coverage * camera.health_score
    if state == camera.zone_id:
        return min(1.0 - EPSILON, camera.sensitivity * operational)
    return min(1.0 - EPSILON, camera.false_positive_rate * operational)


def _normalize(weights: Mapping[ZoneState, float]) -> dict[ZoneState, float]:
    total = sum(weights.values())
    if total <= 0.0:
        message = "zone posterior normalization failed"
        raise RuntimeError(message)
    return {state: weight / total for state, weight in weights.items()}


def _update_belief(
    belief: Mapping[ZoneState, float],
    evidence: tuple[CandidateProbabilityEvidence, ...],
    cameras: tuple[CameraObservation, ...],
) -> dict[ZoneState, float]:
    updated = dict(belief)
    for item in evidence:
        updated[item.zone_id] *= _event_likelihood_ratio(item)
        updated = _normalize(updated)
    for camera in cameras:
        if camera.observation is CameraObservationStatus.NOT_SCANNED:
            continue
        for state, probability in tuple(updated.items()):
            detection = _detection_probability(camera, state)
            likelihood = (
                detection
                if camera.observation is CameraObservationStatus.MATCH
                else 1.0 - detection
            )
            updated[state] = probability * max(EPSILON, likelihood)
        updated = _normalize(updated)
    return updated


def _entropy(probabilities: Mapping[ZoneState, float]) -> float:
    return -sum(
        probability * math.log(probability)
        for probability in probabilities.values()
        if probability > 0.0
    )


def _posterior_after_binary_observation(
    belief: Mapping[ZoneState, float],
    camera: CameraObservation,
    *,
    detected: bool,
) -> tuple[float, dict[ZoneState, float]]:
    likelihoods: dict[ZoneState, float] = {}
    for state in belief:
        likelihoods[state] = (
            _detection_probability(camera, state)
            if detected
            else 1.0 - _detection_probability(camera, state)
        )
    observation_probability = sum(
        belief[state] * likelihood for state, likelihood in likelihoods.items()
    )
    weighted: dict[ZoneState, float] = {
        state: belief[state] * likelihood for state, likelihood in likelihoods.items()
    }
    return observation_probability, _normalize(weighted)


def _camera_rankings(
    belief: Mapping[ZoneState, float],
    cameras: tuple[CameraObservation, ...],
) -> tuple[RankedCamera, ...]:
    prior_entropy = _entropy(belief)
    rankings: list[RankedCamera] = []
    for camera in cameras:
        if (
            not camera.available
            or camera.already_scanned
            or camera.observation is not CameraObservationStatus.NOT_SCANNED
        ):
            continue
        hit_probability, hit_posterior = _posterior_after_binary_observation(
            belief, camera, detected=True
        )
        miss_probability, miss_posterior = _posterior_after_binary_observation(
            belief, camera, detected=False
        )
        information_gain = max(
            0.0,
            prior_entropy
            - (hit_probability * _entropy(hit_posterior))
            - (miss_probability * _entropy(miss_posterior)),
        )
        operational_factor = (
            camera.recording_coverage
            * camera.health_score
            * camera.freshness_score
            * (0.5 + 0.5 * camera.route_centrality)
        )
        rankings.append(
            RankedCamera(
                camera_id=camera.camera_id,
                zone_id=camera.zone_id,
                position=camera.position,
                zone_probability=round(belief[camera.zone_id], 12),
                expected_information_gain=round(information_gain, 12),
                operational_factor=round(operational_factor, 12),
                utility=round(belief[camera.zone_id] * operational_factor, 12),
            )
        )
    return tuple(
        sorted(
            rankings,
            key=lambda item: (
                -item.utility,
                -item.expected_information_gain,
                item.zone_id,
                item.position,
                item.camera_id,
            ),
        )
    )


def assess_zone_probability(request: ZoneProbabilityRequest) -> ZoneProbabilityResponse:
    selected_evidence, suppressed = _deduplicate_tracks(request.evidence)
    initial = _initial_belief(request)
    predicted = _predict_motion(initial, request) if request.advance_motion else initial
    posterior = _update_belief(predicted, selected_evidence, request.cameras)
    assessments = tuple(
        CandidateAssessment(
            event_id=item.event_id,
            track_id=item.track_id,
            zone_id=item.zone_id,
            match_probability=round(
                _candidate_probability(
                    request.candidate_prior_probability,
                    _event_likelihood_ratio(item),
                ),
                12,
            ),
            likelihood_ratio=round(_event_likelihood_ratio(item), 12),
            priority_band=_priority_band(
                _candidate_probability(
                    request.candidate_prior_probability,
                    _event_likelihood_ratio(item),
                )
            ),
            signal_count=len(item.signals),
        )
        for item in selected_evidence
    )
    ranked_cameras = _camera_rankings(posterior, request.cameras)
    return ZoneProbabilityResponse(
        case_id=request.case_id,
        routing_revision=request.routing_revision,
        candidate_assessments=assessments,
        suppressed_correlated_event_ids=suppressed,
        zone_posterior=tuple(
            ZonePosteriorItem(zone_id=zone_id, probability=round(posterior[zone_id], 12))
            for zone_id in range(1, request.zone_count + 1)
        ),
        outside_probability=round(posterior[OUTSIDE], 12),
        unknown_probability=round(posterior[UNKNOWN], 12),
        ranked_cameras=ranked_cameras,
        next_camera_id=ranked_cameras[0].camera_id if ranked_cameras else None,
    )
