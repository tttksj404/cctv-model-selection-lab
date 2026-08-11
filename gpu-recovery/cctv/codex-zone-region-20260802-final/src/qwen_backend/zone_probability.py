"""Keep posterior and camera-ranking invariants in one pure policy module.

# noqa: SIZE_OK
"""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Mapping
from typing import Final, Literal, TypeAlias

from .zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateAssessment,
    CandidatePoolStatus,
    CandidatePriorityBand,
    CandidateProbabilityEvidence,
    EvidenceDeduplicationState,
    RankedCamera,
    ZoneCandidateSummary,
    ZonePosteriorItem,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
    sha256_identifier,
)

ZoneState: TypeAlias = int | Literal["outside", "unknown"]
OUTSIDE: Final[Literal["outside"]] = "outside"
UNKNOWN: Final[Literal["unknown"]] = "unknown"
EPSILON: Final = 1e-9
MAX_LIKELIHOOD_RATIO: Final = 1_000.0
CAMERA_OBSERVATION_RELIABILITY: Final = 0.40
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
        grouped[item.correlation_group_id].append(item)
    selected: list[CandidateProbabilityEvidence] = []
    suppressed: list[str] = []
    for track_key in sorted(grouped):
        ranked = sorted(
            grouped[track_key],
            key=lambda item: (
                -abs(_event_log_likelihood_ratio(item)),
                item.event_id,
            ),
        )
        selected.append(ranked[0])
        suppressed.extend(item.event_id for item in ranked[1:])
    return tuple(selected), tuple(sorted(suppressed))


def _exclude_previously_applied_evidence(
    evidence: tuple[CandidateProbabilityEvidence, ...],
    state: EvidenceDeduplicationState | None,
) -> tuple[
    tuple[CandidateProbabilityEvidence, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
]:
    if state is None:
        return evidence, (), (), ()
    prior_events = frozenset(state.event_id_digests)
    prior_correlations = frozenset(state.correlation_group_digests)
    prior_observations = frozenset(state.observation_group_digests)
    unseen: list[CandidateProbabilityEvidence] = []
    replayed: list[str] = []
    correlated: list[str] = []
    alternatives: list[str] = []
    for item in evidence:
        if sha256_identifier(item.event_id) in prior_events:
            replayed.append(item.event_id)
        elif sha256_identifier(item.correlation_group_id) in prior_correlations:
            correlated.append(item.event_id)
        elif sha256_identifier(item.observation_group_id) in prior_observations:
            alternatives.append(item.event_id)
        else:
            unseen.append(item)
    return (
        tuple(unseen),
        tuple(sorted(replayed)),
        tuple(sorted(correlated)),
        tuple(sorted(alternatives)),
    )


def _next_deduplication_state(
    request: ZoneProbabilityRequest,
) -> EvidenceDeduplicationState:
    previous = request.previous_deduplication_state
    event_digests = set(previous.event_id_digests if previous is not None else ())
    correlation_digests = set(
        previous.correlation_group_digests if previous is not None else ()
    )
    observation_digests = set(
        previous.observation_group_digests if previous is not None else ()
    )
    event_digests.update(sha256_identifier(item.event_id) for item in request.evidence)
    correlation_digests.update(
        sha256_identifier(item.correlation_group_id) for item in request.evidence
    )
    observation_digests.update(
        sha256_identifier(item.observation_group_id) for item in request.evidence
    )
    return EvidenceDeduplicationState(
        source_routing_revision=request.routing_revision,
        event_id_digests=tuple(sorted(event_digests)),
        correlation_group_digests=tuple(sorted(correlation_digests)),
        observation_group_digests=tuple(sorted(observation_digests)),
    )


def _select_observation_representatives(
    evidence: tuple[CandidateProbabilityEvidence, ...],
) -> tuple[tuple[CandidateProbabilityEvidence, ...], tuple[str, ...]]:
    grouped: defaultdict[str, list[CandidateProbabilityEvidence]] = defaultdict(list)
    for item in evidence:
        grouped[item.observation_group_id].append(item)
    selected: list[CandidateProbabilityEvidence] = []
    suppressed: list[str] = []
    for observation_group_id in sorted(grouped):
        ranked = sorted(
            grouped[observation_group_id],
            key=lambda item: (-_event_log_likelihood_ratio(item), item.event_id),
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


def _predict_motion_once(
    belief: Mapping[ZoneState, float],
    request: ZoneProbabilityRequest,
    neighbors: Mapping[int, tuple[int, ...]],
) -> dict[ZoneState, float]:
    predicted: dict[ZoneState, float] = {
        state: 0.0
        for state in (*range(1, request.zone_count + 1), OUTSIDE, UNKNOWN)
    }
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


def _predict_motion(
    belief: Mapping[ZoneState, float],
    request: ZoneProbabilityRequest,
) -> dict[ZoneState, float]:
    elapsed_steps = request.motion_elapsed_seconds / request.motion_step_seconds
    full_steps = math.floor(elapsed_steps)
    fractional_step = elapsed_steps - full_steps
    predicted = dict(belief)
    neighbors = _adjacency(request)
    for _ in range(full_steps):
        predicted = _predict_motion_once(predicted, request, neighbors)
    if fractional_step > 0.0:
        next_step = _predict_motion_once(predicted, request, neighbors)
        predicted = {
            state: ((1.0 - fractional_step) * predicted[state])
            + (fractional_step * next_step[state])
            for state in predicted
        }
    return _normalize(predicted)


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
            updated[state] = probability * (
                max(EPSILON, likelihood) ** CAMERA_OBSERVATION_RELIABILITY
            )
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
    observation_likelihoods: dict[ZoneState, float] = {}
    update_likelihoods: dict[ZoneState, float] = {}
    for state in belief:
        observation_likelihoods[state] = (
            _detection_probability(camera, state)
            if detected
            else 1.0 - _detection_probability(camera, state)
        )
        update_likelihoods[state] = (
            max(EPSILON, observation_likelihoods[state])
            ** CAMERA_OBSERVATION_RELIABILITY
        )
    observation_probability = sum(
        belief[state] * likelihood
        for state, likelihood in observation_likelihoods.items()
    )
    weighted: dict[ZoneState, float] = {
        state: belief[state] * likelihood for state, likelihood in update_likelihoods.items()
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


def _candidate_assessments(
    evidence: tuple[CandidateProbabilityEvidence, ...],
    used_event_ids: frozenset[str],
    candidate_prior_probability: float,
) -> tuple[CandidateAssessment, ...]:
    assessments: list[CandidateAssessment] = []
    for item in evidence:
        likelihood_ratio = _event_likelihood_ratio(item)
        match_probability = _candidate_probability(
            candidate_prior_probability, likelihood_ratio
        )
        assessments.append(
            CandidateAssessment(
                event_id=item.event_id,
                track_id=item.track_id,
                zone_id=item.zone_id,
                camera_id=item.camera_id,
                observation_group_id=item.observation_group_id,
                observed_at=item.observed_at,
                match_probability=round(match_probability, 12),
                likelihood_ratio=round(likelihood_ratio, 12),
                priority_band=_priority_band(match_probability),
                signal_count=len(item.signals),
                used_for_zone_update=item.event_id in used_event_ids,
            )
        )
    return tuple(
        sorted(
            assessments,
            key=lambda item: (-item.match_probability, item.event_id),
        )
    )


def _candidate_pool_status(
    assessments: tuple[CandidateAssessment, ...],
) -> CandidatePoolStatus:
    if any(item.priority_band is CandidatePriorityBand.HIGH_PRIORITY for item in assessments):
        return CandidatePoolStatus.CANDIDATE_FOUND
    if any(item.priority_band is CandidatePriorityBand.REVIEW for item in assessments):
        return CandidatePoolStatus.REVIEW_REQUIRED
    return CandidatePoolStatus.SEARCH_BROADLY


def _zone_candidate_summaries(
    assessments: tuple[CandidateAssessment, ...],
    posterior: Mapping[ZoneState, float],
    zone_count: int,
) -> tuple[ZoneCandidateSummary, ...]:
    return tuple(
        ZoneCandidateSummary(
            zone_id=zone_id,
            candidate_count=len(zone_candidates),
            top_candidate_event_id=(zone_candidates[0].event_id if zone_candidates else None),
            top_candidate_match_probability=(
                zone_candidates[0].match_probability if zone_candidates else None
            ),
            zone_presence_probability=round(posterior[zone_id], 12),
        )
        for zone_id in range(1, zone_count + 1)
        for zone_candidates in (
            tuple(item for item in assessments if item.zone_id == zone_id),
        )
    )


def assess_zone_probability(request: ZoneProbabilityRequest) -> ZoneProbabilityResponse:
    (
        unseen_evidence,
        suppressed_replayed,
        previously_correlated,
        previous_alternatives,
    ) = _exclude_previously_applied_evidence(
        request.evidence, request.previous_deduplication_state
    )
    candidate_evidence, suppressed_correlated = _deduplicate_tracks(unseen_evidence)
    zone_evidence, suppressed_alternatives = _select_observation_representatives(
        candidate_evidence
    )
    initial = _initial_belief(request)
    predicted = _predict_motion(initial, request) if request.advance_motion else initial
    posterior = _update_belief(predicted, zone_evidence, request.cameras)
    assessments = _candidate_assessments(
        candidate_evidence,
        frozenset(item.event_id for item in zone_evidence),
        request.candidate_prior_probability,
    )
    most_likely_zone_id = max(
        range(1, request.zone_count + 1),
        key=lambda zone_id: (posterior[zone_id], -zone_id),
    )
    ranked_cameras = _camera_rankings(posterior, request.cameras)
    return ZoneProbabilityResponse(
        case_id=request.case_id,
        routing_revision=request.routing_revision,
        candidate_assessments=assessments,
        candidate_pool_status=_candidate_pool_status(assessments),
        deduplication_state=_next_deduplication_state(request),
        suppressed_replayed_event_ids=suppressed_replayed,
        suppressed_correlated_event_ids=tuple(
            sorted((*previously_correlated, *suppressed_correlated))
        ),
        suppressed_alternative_event_ids=tuple(
            sorted((*previous_alternatives, *suppressed_alternatives))
        ),
        zone_posterior=tuple(
            ZonePosteriorItem(zone_id=zone_id, probability=round(posterior[zone_id], 12))
            for zone_id in range(1, request.zone_count + 1)
        ),
        zone_candidate_summaries=_zone_candidate_summaries(
            assessments, posterior, request.zone_count
        ),
        most_likely_zone_id=most_likely_zone_id,
        most_likely_zone_probability=round(posterior[most_likely_zone_id], 12),
        posterior_entropy=round(_entropy(posterior), 12),
        outside_probability=round(posterior[OUTSIDE], 12),
        unknown_probability=round(posterior[UNKNOWN], 12),
        ranked_cameras=ranked_cameras,
        next_camera_id=ranked_cameras[0].camera_id if ranked_cameras else None,
    )
