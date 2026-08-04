"""Run one sealed replay with scenario generation and metric provenance together.

# noqa: SIZE_OK
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import statistics
from collections import defaultdict
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, TypeAlias, assert_never, cast

from qwen_backend.zone_probability import (
    CAMERA_OBSERVATION_RELIABILITY,
    assess_zone_probability,
)
from qwen_backend.zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateProbabilityEvidence,
    EvidenceDeduplicationState,
    ProbabilitySignal,
    ProbabilitySignalKind,
    ZoneBeliefInput,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
)

if __package__:
    from scripts.zone_policy_paired_evidence import write_paired_records
    from scripts.zone_policy_replay_seed import TargetState, target_state_from_rng
    from scripts.zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        EXPECTED_PAIRED_EVIDENCE_SHA256,
        EXPECTED_PUBLIC_REID_CANONICAL_SHA256,
        OPERATING_POINT_VALUES,
        POLICIES,
        PROMOTION_REASON,
        REPLAY_KIND,
        RUNTIME_POLICY_IDS,
        SCENARIOS,
        JsonValue,
        PolicyName,
        canonical_json_sha256,
        canonical_json_sha256_value,
        parse_json_bytes,
        runtime_policy_implemented,
    )
    from scripts.zone_policy_result_schema import (
        passes_paired_promotion_gate as _passes_paired_promotion_gate,
    )
else:
    from zone_policy_paired_evidence import write_paired_records
    from zone_policy_replay_seed import TargetState, target_state_from_rng
    from zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        EXPECTED_PAIRED_EVIDENCE_SHA256,
        EXPECTED_PUBLIC_REID_CANONICAL_SHA256,
        OPERATING_POINT_VALUES,
        POLICIES,
        PROMOTION_REASON,
        REPLAY_KIND,
        RUNTIME_POLICY_IDS,
        SCENARIOS,
        JsonValue,
        PolicyName,
        canonical_json_sha256,
        canonical_json_sha256_value,
        parse_json_bytes,
        runtime_policy_implemented,
    )
    from zone_policy_result_schema import (
        passes_paired_promotion_gate as _passes_paired_promotion_gate,
    )

CohortName: TypeAlias = Literal["selection", "sealed_test"]
HASH_PLACEHOLDER = "0" * 64
MAX_SCANS = EXPECTED_MAX_SCANS


class ReplayConfigurationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class OperatingPoint:
    name: str
    sensitivity: float
    false_positive_rate: float
    unavailable_rate: float


@dataclass(frozen=True, slots=True)
class ReplayCamera:
    camera_id: str
    zone_id: int
    position: int
    available: bool
    recording_coverage: float
    health_score: float
    freshness_score: float
    route_centrality: float
    sensitivity: float
    false_positive_rate: float
    operating_point_id: str
    operating_point_sha256: str

    @property
    def operational_factor(self) -> float:
        return (
            self.recording_coverage
            * self.health_score
            * self.freshness_score
            * (0.5 + 0.5 * self.route_centrality)
        )

    def as_observation(
        self,
        *,
        status: CameraObservationStatus = CameraObservationStatus.NOT_SCANNED,
        already_scanned: bool = False,
    ) -> CameraObservation:
        return CameraObservation(
            camera_id=self.camera_id,
            zone_id=self.zone_id,
            position=self.position,
            available=self.available,
            recording_coverage=self.recording_coverage,
            health_score=self.health_score,
            freshness_score=self.freshness_score,
            route_centrality=self.route_centrality,
            sensitivity=self.sensitivity,
            false_positive_rate=self.false_positive_rate,
            operating_point_id=self.operating_point_id,
            operating_point_sha256=self.operating_point_sha256,
            validation_sample_count=57,
            already_scanned=already_scanned,
            observation=status,
        )


@dataclass(frozen=True, slots=True)
class EpisodeOutcome:
    cohort: CohortName
    episode_id: str
    scenario: str
    operating_point: str
    policy: PolicyName
    target_state: TargetState
    scans_to_resolution: int
    resolved_within_budget: bool
    final_top1_correct: bool
    false_zone_activation: bool


@dataclass(frozen=True, slots=True)
class AggregateMetrics:
    episodes: int
    resolved_within_budget_rate: float
    final_top1_accuracy: float
    false_zone_activation_rate: float
    mean_scans_to_resolution: float
    p95_scans_to_resolution: float


def _canonical_json_sha256(path: Path) -> str:
    return canonical_json_sha256(path)


def _operating_hash(point: OperatingPoint) -> str:
    payload = json.dumps(asdict(point), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _prior(
    rng: random.Random,
    scenario: str,
    target: TargetState,
) -> tuple[tuple[ZoneBeliefInput, ...], float, float]:
    if scenario == "location_certain":
        expected = target if isinstance(target, int) and rng.random() < 0.85 else rng.randint(1, 4)
        zone_values = {zone_id: 0.05 for zone_id in range(1, 5)}
        zone_values[expected] = 0.70
        return (
            tuple(
                ZoneBeliefInput(zone_id=zone_id, probability=zone_values[zone_id])
                for zone_id in range(1, 5)
            ),
            0.10,
            0.05,
        )
    if scenario == "recording_only_or_outside":
        return (
            tuple(ZoneBeliefInput(zone_id=zone_id, probability=0.10) for zone_id in range(1, 5)),
            0.40,
            0.20,
        )
    return (
        tuple(ZoneBeliefInput(zone_id=zone_id, probability=0.20) for zone_id in range(1, 5)),
        0.10,
        0.10,
    )


def _cameras(rng: random.Random, point: OperatingPoint) -> tuple[ReplayCamera, ...]:
    operating_sha = _operating_hash(point)
    cameras: list[ReplayCamera] = []
    for zone_id in range(1, 5):
        for position in range(1, 5):
            available = position == 1 or rng.random() >= point.unavailable_rate
            cameras.append(
                ReplayCamera(
                    camera_id=f"{zone_id}-{position}",
                    zone_id=zone_id,
                    position=position,
                    available=available,
                    recording_coverage=rng.uniform(0.68, 1.0),
                    health_score=rng.uniform(0.72, 1.0),
                    freshness_score=rng.uniform(0.75, 1.0),
                    route_centrality=(
                        rng.uniform(0.62, 0.95) if position == 1 else rng.uniform(0.35, 0.82)
                    ),
                    sensitivity=point.sensitivity,
                    false_positive_rate=point.false_positive_rate,
                    operating_point_id=point.name,
                    operating_point_sha256=operating_sha,
                )
            )
    return tuple(cameras)


def _candidate_evidence(
    rng: random.Random,
    episode_id: str,
    target: TargetState,
    point: OperatingPoint,
    model_sha256: str,
) -> tuple[CandidateProbabilityEvidence, ...]:
    zone_id: int | None = None
    probability = 0.10
    if isinstance(target, int) and rng.random() < point.sensitivity:
        zone_id = target
        probability = rng.uniform(0.68, 0.96)
    elif rng.random() < point.false_positive_rate:
        zone_id = rng.randint(1, 4)
        if zone_id == target:
            zone_id = (zone_id % 4) + 1
        probability = rng.uniform(0.18, 0.78)
    if zone_id is None:
        return ()
    signal = ProbabilitySignal(
        signal_kind=ProbabilitySignalKind.REID,
        probability=probability,
        calibration_base_rate=0.10,
        reliability=1.0,
        model_id="solider-swin-b-msmt17",
        model_sha256=model_sha256,
        calibrator_id="prid2011-validation-lr-v1",
        calibrator_sha256=model_sha256,
        calibration_manifest_sha256=model_sha256,
        calibration_sample_count=57,
    )
    return (
        CandidateProbabilityEvidence(
            event_id=f"{episode_id}:candidate",
            zone_id=zone_id,
            camera_id=f"{zone_id}-1",
            track_id=f"{episode_id}:track",
            correlation_group_id=f"{episode_id}:global-track",
            observation_group_id=f"{episode_id}:camera-{zone_id}-1:segment-1",
            observed_at=datetime(2026, 8, 1, 3, 0, tzinfo=UTC),
            track_quality=rng.uniform(0.65, 1.0),
            signals=(signal,),
        ),
    )


def _request(
    *,
    episode_id: str,
    cameras: tuple[ReplayCamera, ...],
    evidence: tuple[CandidateProbabilityEvidence, ...],
    prior: tuple[tuple[ZoneBeliefInput, ...], float, float],
    scanned: frozenset[str] = frozenset(),
    observed_camera_id: str | None = None,
    observed_status: CameraObservationStatus = CameraObservationStatus.NOT_SCANNED,
    previous_deduplication_state: EvidenceDeduplicationState | None = None,
) -> ZoneProbabilityRequest:
    zone_prior, outside_prior, unknown_prior = prior
    observations = tuple(
        camera.as_observation(
            status=(
                observed_status
                if camera.camera_id == observed_camera_id
                else CameraObservationStatus.NOT_SCANNED
            ),
            already_scanned=camera.camera_id in scanned and camera.camera_id != observed_camera_id,
        )
        for camera in cameras
    )
    return ZoneProbabilityRequest(
        case_id=episode_id,
        routing_revision=len(scanned) + 1,
        active_routing_revision=(
            previous_deduplication_state.source_routing_revision
            if previous_deduplication_state is not None
            else 0
        ),
        zone_count=4,
        candidate_prior_probability=0.10,
        advance_motion=False,
        previous_zone_posterior=zone_prior,
        previous_outside_probability=outside_prior,
        previous_unknown_probability=unknown_prior,
        previous_deduplication_state=previous_deduplication_state,
        evidence=evidence,
        cameras=observations,
    )


def _response_prior(
    response: ZoneProbabilityResponse,
) -> tuple[tuple[ZoneBeliefInput, ...], float, float]:
    return (
        tuple(
            ZoneBeliefInput(zone_id=item.zone_id, probability=item.probability)
            for item in response.zone_posterior
        ),
        response.outside_probability,
        response.unknown_probability,
    )


def _top_state(response: ZoneProbabilityResponse) -> tuple[TargetState, float]:
    values: list[tuple[TargetState, float]] = [
        (item.zone_id, item.probability) for item in response.zone_posterior
    ]
    values.extend(
        (("outside", response.outside_probability), ("unknown", response.unknown_probability))
    )
    return max(values, key=lambda item: item[1])


def _is_false_zone_activation(
    response: ZoneProbabilityResponse,
    target: TargetState,
) -> bool:
    top_state, top_probability = _top_state(response)
    return isinstance(top_state, int) and top_state != target and top_probability >= 0.75


def _risk_adjusted_detection_score(
    camera: ReplayCamera,
    zone_probabilities: Mapping[int, float],
    false_hit_penalty: float,
) -> tuple[float, float, int, int, str]:
    zone_probability = zone_probabilities.get(camera.zone_id, 0.0)
    operational_probability = camera.recording_coverage * camera.health_score
    expected_true_hit = zone_probability * camera.sensitivity * operational_probability
    expected_false_hit = (
        (1.0 - zone_probability) * camera.false_positive_rate * operational_probability
    )
    return (
        expected_true_hit - false_hit_penalty * expected_false_hit,
        expected_true_hit,
        -camera.zone_id,
        -camera.position,
        camera.camera_id,
    )


def _expected_bayes_utilities(
    camera: ReplayCamera,
    response: ZoneProbabilityResponse,
) -> tuple[float, float]:
    belief: dict[TargetState, float] = {
        item.zone_id: item.probability for item in response.zone_posterior
    }
    belief["outside"] = response.outside_probability
    belief["unknown"] = response.unknown_probability
    operational_probability = camera.recording_coverage * camera.health_score

    def outcome(detected: bool) -> tuple[float, float]:
        observation_probability = 0.0
        posterior_weights: list[float] = []
        for state, prior_probability in belief.items():
            detection_probability = (
                camera.sensitivity * operational_probability
                if state == camera.zone_id
                else camera.false_positive_rate * operational_probability
            )
            likelihood = detection_probability if detected else 1.0 - detection_probability
            observation_probability += prior_probability * likelihood
            posterior_weights.append(
                prior_probability * (max(1e-9, likelihood) ** CAMERA_OBSERVATION_RELIABILITY)
            )
        normalizer = sum(posterior_weights)
        top_probability = max(posterior_weights) / normalizer
        return observation_probability, top_probability

    hit_probability, hit_top_probability = outcome(detected=True)
    miss_probability, miss_top_probability = outcome(detected=False)
    expected_accuracy = (
        hit_probability * hit_top_probability + miss_probability * miss_top_probability
    )
    expected_resolution = hit_probability * (
        hit_top_probability if hit_top_probability >= 0.55 else 0.0
    ) + miss_probability * (miss_top_probability if miss_top_probability >= 0.55 else 0.0)
    return expected_accuracy, expected_resolution


def _expected_resolution_score(
    camera: ReplayCamera,
    response: ZoneProbabilityResponse,
) -> tuple[float, float, int, int]:
    expected_accuracy, expected_resolution = _expected_bayes_utilities(camera, response)
    return expected_resolution, expected_accuracy, -camera.zone_id, -camera.position


def _choose_camera(
    policy: PolicyName,
    response: ZoneProbabilityResponse,
    cameras: tuple[ReplayCamera, ...],
    scanned: frozenset[str],
) -> ReplayCamera | None:
    remaining = tuple(
        camera for camera in cameras if camera.available and camera.camera_id not in scanned
    )
    if not remaining:
        return None
    ranking_by_id = {item.camera_id: item for item in response.ranked_cameras}
    zone_probabilities = {item.zone_id: item.probability for item in response.zone_posterior}
    ranked_remaining = tuple(camera for camera in remaining if camera.camera_id in ranking_by_id)
    information_weight: float
    match policy:
        case "static_representative":
            return min(
                remaining,
                key=lambda camera: (camera.position, camera.zone_id, camera.camera_id),
            )
        case "deployed_runtime":
            return next(
                (camera for camera in remaining if camera.camera_id == response.next_camera_id),
                None,
            )
        case "pure_information_gain":
            if not ranked_remaining:
                return None
            return max(
                ranked_remaining,
                key=lambda camera: (
                    ranking_by_id[camera.camera_id].expected_information_gain,
                    camera.camera_id == response.next_camera_id,
                    -camera.zone_id,
                    -camera.position,
                ),
            )
        case "expected_detection":
            return max(
                remaining,
                key=lambda camera: _risk_adjusted_detection_score(camera, zone_probabilities, 0.0),
            )
        case "risk_adjusted_detection_0_5":
            return max(
                remaining,
                key=lambda camera: _risk_adjusted_detection_score(camera, zone_probabilities, 0.5),
            )
        case "risk_adjusted_detection_1_0":
            return max(
                remaining,
                key=lambda camera: _risk_adjusted_detection_score(camera, zone_probabilities, 1.0),
            )
        case "risk_adjusted_detection_2_0":
            return max(
                remaining,
                key=lambda camera: _risk_adjusted_detection_score(camera, zone_probabilities, 2.0),
            )
        case "expected_bayes_accuracy":
            return max(
                remaining,
                key=lambda camera: (
                    *_expected_bayes_utilities(camera, response),
                    -camera.zone_id,
                    -camera.position,
                ),
            )
        case "expected_resolution_0_55":
            return max(
                remaining,
                key=lambda camera: _expected_resolution_score(camera, response),
            )
        case "hybrid_eig_0_25":
            information_weight = 0.25
        case "hybrid_eig_0_50":
            information_weight = 0.50
        case "hybrid_eig_0_75":
            information_weight = 0.75
        case _:
            assert_never(policy)
    if not ranked_remaining:
        return None
    utilities = tuple(ranking_by_id[camera.camera_id].utility for camera in ranked_remaining)
    information_gains = tuple(
        ranking_by_id[camera.camera_id].expected_information_gain for camera in ranked_remaining
    )
    utility_min, utility_max = min(utilities), max(utilities)
    information_min, information_max = min(information_gains), max(information_gains)

    def normalize(value: float, minimum: float, maximum: float) -> float:
        span = maximum - minimum
        return 1.0 if span <= 1e-12 else (value - minimum) / span

    return max(
        ranked_remaining,
        key=lambda camera: (
            (1.0 - information_weight)
            * normalize(ranking_by_id[camera.camera_id].utility, utility_min, utility_max)
            + information_weight
            * normalize(
                ranking_by_id[camera.camera_id].expected_information_gain,
                information_min,
                information_max,
            ),
            ranking_by_id[camera.camera_id].utility,
            ranking_by_id[camera.camera_id].expected_information_gain,
            -camera.zone_id,
            -camera.position,
        ),
    )


def _observation_status(
    target: TargetState,
    camera: ReplayCamera,
    uniform_draw: float,
) -> CameraObservationStatus:
    operational = camera.recording_coverage * camera.health_score
    detection_probability = (
        camera.sensitivity * operational
        if target == camera.zone_id
        else camera.false_positive_rate * operational
    )
    return (
        CameraObservationStatus.MATCH
        if uniform_draw < detection_probability
        else CameraObservationStatus.NO_MATCH
    )


def make_prior(
    rng: random.Random,
    scenario: str,
    target: TargetState,
) -> tuple[tuple[ZoneBeliefInput, ...], float, float]:
    return _prior(rng, scenario, target)


def make_cameras(rng: random.Random, point: OperatingPoint) -> tuple[ReplayCamera, ...]:
    return _cameras(rng, point)


def make_candidate_evidence(
    rng: random.Random,
    episode_id: str,
    target: TargetState,
    point: OperatingPoint,
    model_sha256: str,
) -> tuple[CandidateProbabilityEvidence, ...]:
    return _candidate_evidence(rng, episode_id, target, point, model_sha256)


def make_request(
    *,
    episode_id: str,
    cameras: tuple[ReplayCamera, ...],
    evidence: tuple[CandidateProbabilityEvidence, ...],
    prior: tuple[tuple[ZoneBeliefInput, ...], float, float],
    scanned: frozenset[str] = frozenset(),
    observed_camera_id: str | None = None,
    observed_status: CameraObservationStatus = CameraObservationStatus.NOT_SCANNED,
    previous_deduplication_state: EvidenceDeduplicationState | None = None,
) -> ZoneProbabilityRequest:
    return _request(
        episode_id=episode_id,
        cameras=cameras,
        evidence=evidence,
        prior=prior,
        scanned=scanned,
        observed_camera_id=observed_camera_id,
        observed_status=observed_status,
        previous_deduplication_state=previous_deduplication_state,
    )


def response_prior(
    response: ZoneProbabilityResponse,
) -> tuple[tuple[ZoneBeliefInput, ...], float, float]:
    return _response_prior(response)


def choose_camera(
    policy: Literal[
        "static_representative",
        "deployed_runtime",
        "expected_bayes_accuracy",
    ],
    response: ZoneProbabilityResponse,
    cameras: tuple[ReplayCamera, ...],
    scanned: frozenset[str],
) -> ReplayCamera | None:
    return _choose_camera(cast(PolicyName, policy), response, cameras, scanned)


def observation_status(
    target: TargetState,
    camera: ReplayCamera,
    uniform_draw: float,
) -> CameraObservationStatus:
    return _observation_status(target, camera, uniform_draw)


def _run_episode(
    *,
    episode_id: str,
    cohort: CohortName,
    scenario: str,
    point: OperatingPoint,
    policy: PolicyName,
    target: TargetState,
    cameras: tuple[ReplayCamera, ...],
    evidence: tuple[CandidateProbabilityEvidence, ...],
    prior: tuple[tuple[ZoneBeliefInput, ...], float, float],
    observation_draws: dict[str, float],
) -> EpisodeOutcome:
    response = assess_zone_probability(
        _request(
            episode_id=episode_id,
            cameras=cameras,
            evidence=evidence,
            prior=prior,
        )
    )
    scanned: frozenset[str] = frozenset()
    resolved_at = MAX_SCANS + 1
    false_activation = False
    for scan_index in range(1, MAX_SCANS + 1):
        false_activation = false_activation or _is_false_zone_activation(response, target)
        camera = _choose_camera(policy, response, cameras, scanned)
        if camera is None:
            break
        status = _observation_status(target, camera, observation_draws[camera.camera_id])
        scanned = scanned | {camera.camera_id}
        response = assess_zone_probability(
            _request(
                episode_id=episode_id,
                cameras=cameras,
                evidence=(),
                prior=_response_prior(response),
                scanned=scanned,
                observed_camera_id=camera.camera_id,
                observed_status=status,
                previous_deduplication_state=response.deduplication_state,
            )
        )
        false_activation = false_activation or _is_false_zone_activation(response, target)
        top_state, top_probability = _top_state(response)
        if top_state == target and top_probability >= 0.55 and resolved_at > MAX_SCANS:
            resolved_at = scan_index
    final_top_state, _ = _top_state(response)
    return EpisodeOutcome(
        cohort=cohort,
        episode_id=episode_id,
        scenario=scenario,
        operating_point=point.name,
        policy=policy,
        target_state=target,
        scans_to_resolution=resolved_at,
        resolved_within_budget=resolved_at <= MAX_SCANS,
        final_top1_correct=final_top_state == target,
        false_zone_activation=false_activation,
    )


def _aggregate(outcomes: list[EpisodeOutcome]) -> AggregateMetrics:
    scans = sorted(outcome.scans_to_resolution for outcome in outcomes)
    p95_index = min(len(scans) - 1, math.ceil(0.95 * len(scans)) - 1)
    return AggregateMetrics(
        episodes=len(outcomes),
        resolved_within_budget_rate=statistics.fmean(
            outcome.resolved_within_budget for outcome in outcomes
        ),
        final_top1_accuracy=statistics.fmean(outcome.final_top1_correct for outcome in outcomes),
        false_zone_activation_rate=statistics.fmean(
            outcome.false_zone_activation for outcome in outcomes
        ),
        mean_scans_to_resolution=statistics.fmean(scans),
        p95_scans_to_resolution=float(scans[p95_index]),
    )


def _round_metrics(metrics: AggregateMetrics) -> dict[str, int | float]:
    return {
        "episodes": metrics.episodes,
        "resolvedWithinBudgetRate": round(metrics.resolved_within_budget_rate, 6),
        "finalTop1Accuracy": round(metrics.final_top1_accuracy, 6),
        "falseZoneActivationRate": round(metrics.false_zone_activation_rate, 6),
        "meanScansToResolution": round(metrics.mean_scans_to_resolution, 6),
        "p95ScansToResolution": round(metrics.p95_scans_to_resolution, 6),
    }


def _difference_interval(values: list[float]) -> dict[str, bool | float]:
    mean = statistics.fmean(values)
    standard_error = statistics.stdev(values) / math.sqrt(len(values)) if len(values) > 1 else 0.0
    radius = 1.96 * standard_error
    lower = mean - radius
    upper = mean + radius
    return {
        "delta": mean,
        "delta95Lower": lower,
        "delta95Upper": upper,
        "includesZero": lower <= 0.0 <= upper,
    }


def _paired_comparison(
    candidate: list[EpisodeOutcome],
    baseline: list[EpisodeOutcome],
) -> dict[str, dict[str, bool | float]]:
    baseline_by_episode = {outcome.episode_id: outcome for outcome in baseline}
    candidate_by_episode = {outcome.episode_id: outcome for outcome in candidate}
    if candidate_by_episode.keys() != baseline_by_episode.keys():
        raise ReplayConfigurationError("paired policy outcomes must share episode IDs")

    def differences(extract: Callable[[EpisodeOutcome], float]) -> list[float]:
        return [
            extract(candidate_by_episode[episode_id]) - extract(baseline_by_episode[episode_id])
            for episode_id in sorted(candidate_by_episode)
        ]

    return {
        "resolvedWithinBudgetRate": _difference_interval(
            differences(lambda outcome: float(outcome.resolved_within_budget))
        ),
        "finalTop1Accuracy": _difference_interval(
            differences(lambda outcome: float(outcome.final_top1_correct))
        ),
        "falseZoneActivationRate": _difference_interval(
            differences(lambda outcome: float(outcome.false_zone_activation))
        ),
        "meanScansToResolution": _difference_interval(
            differences(lambda outcome: float(outcome.scans_to_resolution))
        ),
    }


def _runtime_policy_for(
    selected: PolicyName,
    proxy_material_improvement: bool,
) -> str:
    runtime_key: PolicyName = (
        selected
        if proxy_material_improvement and runtime_policy_implemented(selected)
        else "deployed_runtime"
    )
    return RUNTIME_POLICY_IDS[runtime_key]


def _public_reid_evidence(path: Path) -> dict[str, str | int | float | bool]:
    source_value = parse_json_bytes(path.read_bytes(), label=f"public ReID evidence {path}")
    if not isinstance(source_value, dict):
        raise ReplayConfigurationError("public ReID evidence schema is invalid")
    payload = source_value
    test_value = payload.get("testMetrics")
    if not isinstance(test_value, dict):
        raise ReplayConfigurationError("public ReID evidence schema is invalid")
    test = test_value
    sealed_count = payload.get("sealedTestEvaluationCount")
    known_queries = test.get("known_queries")
    distractor_queries = test.get("distractor_queries")
    if (
        payload.get("schemaVersion") != "prid2011-solider-open-set-v3-summary"
        or payload.get("status") != "valid"
        or payload.get("cacheMetadataValidated") is not True
        or isinstance(sealed_count, bool)
        or not isinstance(sealed_count, int)
        or isinstance(known_queries, bool)
        or not isinstance(known_queries, int)
        or isinstance(distractor_queries, bool)
        or not isinstance(distractor_queries, int)
    ):
        raise ReplayConfigurationError("public ReID evidence schema is invalid")

    rate_keys = (
        "known_rank1",
        "known_recall_at5",
        "distractor_false_match_rate",
        "automatic_decision_accuracy",
    )
    rates: dict[str, float] = {}
    for key in rate_keys:
        value = test.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ReplayConfigurationError("public ReID evidence metrics are invalid")
        number = float(value)
        if not math.isfinite(number) or not 0 <= number <= 1:
            raise ReplayConfigurationError("public ReID evidence metrics are invalid")
        rates[key] = number
    canonical_hash = canonical_json_sha256_value(source_value)
    if canonical_hash != EXPECTED_PUBLIC_REID_CANONICAL_SHA256:
        raise ReplayConfigurationError("public ReID evidence digest is not trusted")
    return {
        "artifact": path.as_posix(),
        "sha256": canonical_hash,
        "dataset": "PRID2011 public cross-camera proxy",
        "sealedTestEvaluationCount": sealed_count,
        "knownQueries": known_queries,
        "distractorQueries": distractor_queries,
        "knownRank1": rates["known_rank1"],
        "knownRecallAt5": rates["known_recall_at5"],
        "distractorFalseMatchRate": rates["distractor_false_match_rate"],
        "automaticDecisionAccuracy": rates["automatic_decision_accuracy"],
        "projectCctvEvidence": False,
    }


def _runtime_evidence() -> dict[str, str]:
    return {
        "execution": "cpu-deterministic-policy-replay",
        "python": platform.python_version(),
    }


def _paired_record(
    outcome: EpisodeOutcome,
    *,
    base_seed: int,
    scenario_indexes: Mapping[str, int],
    point_indexes: Mapping[str, int],
) -> dict[str, JsonValue]:
    episode_index = int(outcome.episode_id.rsplit(":", maxsplit=1)[1])
    cohort_offset = 0 if outcome.cohort == "selection" else 10_000_000
    cell_seed = (
        base_seed
        + cohort_offset
        + scenario_indexes[outcome.scenario] * 1_000_000
        + point_indexes[outcome.operating_point] * 100_000
        + episode_index
    )
    return {
        "cohort": outcome.cohort,
        "episodeId": outcome.episode_id,
        "episodeIndex": episode_index,
        "cellSeed": cell_seed,
        "scenario": outcome.scenario,
        "operatingPoint": outcome.operating_point,
        "policy": outcome.policy,
        "targetState": outcome.target_state,
        "scansToResolution": outcome.scans_to_resolution,
        "resolvedWithinBudget": outcome.resolved_within_budget,
        "finalTop1Correct": outcome.final_top1_correct,
        "falseZoneActivation": outcome.false_zone_activation,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Selection plus sealed replay of static, deployed, EIG, and hybrid policies"
    )
    parser.add_argument("--episodes-per-cell", type=int, default=125)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--public-reid-result", type=Path, required=True)
    parser.add_argument("--paired-evidence-output", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes_per_cell < 50:
        raise ReplayConfigurationError("episodes-per-cell must be at least 50")

    public_evidence = _public_reid_evidence(args.public_reid_result)
    model_sha = str(public_evidence["sha256"])
    points = tuple(
        OperatingPoint(name, sensitivity, false_positive_rate, unavailable_rate)
        for name, sensitivity, false_positive_rate, unavailable_rate in OPERATING_POINT_VALUES
    )
    scenarios = SCENARIOS
    outcomes: list[EpisodeOutcome] = []
    cohorts: tuple[CohortName, ...] = ("selection", "sealed_test")
    for cohort_index, cohort in enumerate(cohorts):
        for scenario_index, scenario in enumerate(scenarios):
            for point_index, point in enumerate(points):
                for episode_index in range(args.episodes_per_cell):
                    cell_seed = (
                        args.seed
                        + (cohort_index * 10_000_000)
                        + (scenario_index * 1_000_000)
                        + (point_index * 100_000)
                        + episode_index
                    )
                    rng = random.Random(cell_seed)
                    episode_id = f"{cohort}:{scenario}:{point.name}:{episode_index}"
                    target = target_state_from_rng(rng, scenario)
                    prior = _prior(rng, scenario, target)
                    cameras = _cameras(rng, point)
                    evidence = _candidate_evidence(rng, episode_id, target, point, model_sha)
                    draws = {camera.camera_id: rng.random() for camera in cameras}
                    for policy in POLICIES:
                        outcomes.append(
                            _run_episode(
                                episode_id=episode_id,
                                cohort=cohort,
                                scenario=scenario,
                                point=point,
                                policy=policy,
                                target=target,
                                cameras=cameras,
                                evidence=evidence,
                                prior=prior,
                                observation_draws=draws,
                            )
                        )

    scenario_indexes = {scenario: index for index, scenario in enumerate(scenarios)}
    point_indexes = {point.name: index for index, point in enumerate(points)}
    raw_records = [
        _paired_record(
            outcome,
            base_seed=args.seed,
            scenario_indexes=scenario_indexes,
            point_indexes=point_indexes,
        )
        for outcome in outcomes
    ]
    paired_evidence_sha = write_paired_records(args.paired_evidence_output, raw_records)
    if (
        EXPECTED_PAIRED_EVIDENCE_SHA256 != HASH_PLACEHOLDER
        and paired_evidence_sha != EXPECTED_PAIRED_EVIDENCE_SHA256
    ):
        raise ReplayConfigurationError("paired evidence digest changed from the sealed digest")

    by_policy: defaultdict[tuple[CohortName, PolicyName], list[EpisodeOutcome]] = defaultdict(list)
    by_cell: defaultdict[tuple[CohortName, str, str, PolicyName], list[EpisodeOutcome]] = (
        defaultdict(list)
    )
    for outcome in outcomes:
        by_policy[(outcome.cohort, outcome.policy)].append(outcome)
        by_cell[(outcome.cohort, outcome.scenario, outcome.operating_point, outcome.policy)].append(
            outcome
        )
    selection_aggregate = {
        policy: _round_metrics(_aggregate(by_policy[("selection", policy)])) for policy in POLICIES
    }
    selected: PolicyName = min(
        POLICIES,
        key=lambda policy: (
            -float(selection_aggregate[policy]["resolvedWithinBudgetRate"]),
            float(selection_aggregate[policy]["falseZoneActivationRate"]),
            float(selection_aggregate[policy]["meanScansToResolution"]),
        ),
    )
    selection_paired_comparisons = {
        policy: _paired_comparison(
            by_policy[("selection", policy)],
            by_policy[("selection", "deployed_runtime")],
        )
        for policy in POLICIES
        if policy != "deployed_runtime"
    }
    sealed_aggregate = {
        policy: _round_metrics(_aggregate(by_policy[("sealed_test", policy)]))
        for policy in POLICIES
    }
    sealed_paired_comparisons = {
        policy: _paired_comparison(
            by_policy[("sealed_test", policy)],
            by_policy[("sealed_test", "deployed_runtime")],
        )
        for policy in POLICIES
        if policy != "deployed_runtime"
    }
    selection_comparison = selection_paired_comparisons.get(selected)
    selected_comparison = sealed_paired_comparisons.get(selected)
    selection_material_improvement = bool(
        selection_comparison and _passes_paired_promotion_gate(selection_comparison)
    )
    sealed_material_improvement = bool(
        selected_comparison and _passes_paired_promotion_gate(selected_comparison)
    )
    proxy_material_improvement = selection_material_improvement and sealed_material_improvement
    runtime_policy = _runtime_policy_for(selected, proxy_material_improvement)
    result = {
        "schemaVersion": "eyesonu-zone-policy-replay-v3",
        "status": "valid",
        "seed": args.seed,
        "episodesPerCellPerCohort": args.episodes_per_cell,
        "pairedEpisodeCount": len(scenarios) * len(points) * args.episodes_per_cell,
        "publicReidEvidence": public_evidence,
        "pairedOutcomeEvidence": {
            "artifact": args.paired_evidence_output.as_posix(),
            "format": "jsonl-zlib-v1",
            "recordCount": len(raw_records),
            "sha256": paired_evidence_sha,
        },
        "topologyReplayEvidence": {
            "kind": REPLAY_KIND,
            "projectCctvEvidence": False,
            "synchronizedMultiCameraObservation": False,
            "scenarios": list(scenarios),
            "operatingPoints": [asdict(point) for point in points],
            "maxScans": MAX_SCANS,
            "selectionCohort": {
                "seedOffset": 0,
                "aggregateByPolicy": selection_aggregate,
                "pairedComparisonsAgainstDeployed": selection_paired_comparisons,
            },
            "sealedTestCohort": {
                "seedOffset": 10_000_000,
                "aggregateByPolicy": sealed_aggregate,
                "pairedComparisonsAgainstDeployed": sealed_paired_comparisons,
                "byScenarioAndOperatingPoint": {
                    f"{scenario}/{point.name}/{policy}": _round_metrics(
                        _aggregate(by_cell[("sealed_test", scenario, point.name, policy)])
                    )
                    for scenario in scenarios
                    for point in points
                    for policy in POLICIES
                },
            },
        },
        "selectedPolicy": selected,
        "selectedRuntimePolicy": runtime_policy,
        "selectionMetricOrder": [
            "resolvedWithinBudgetRate descending",
            "falseZoneActivationRate ascending",
            "meanScansToResolution ascending",
        ],
        "runtimeSafetyContract": {
            "operatorReviewRequired": True,
            "autoMatchAllowed": False,
            "probabilityProvenanceRequired": True,
            "sameTrackEvidenceDeduplicated": True,
            "staleProbabilityRevisionRejected": True,
            "trustedRegistryAllowlistRequired": True,
            "crossCameraCorrelationGroupRequired": True,
        },
        "runtimeEvidence": _runtime_evidence(),
        "promotionDecision": {
            "projectCctvGeneralization85Confirmed": False,
            "cameraUtilityCausalImprovementConfirmed": False,
            "selectionPairedIntervalPassed": selection_material_improvement,
            "sealedTestPairedIntervalPassed": sealed_material_improvement,
            "proxyMaterialImprovementOverDeployedConfirmed": proxy_material_improvement,
            "reason": PROMOTION_REASON,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "selectedPolicy": selected,
                "selectionAggregate": selection_aggregate,
                "sealedTestAggregate": sealed_aggregate,
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
