from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import random
import statistics
import subprocess
from collections import defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal, TypeAlias

from qwen_backend.zone_probability import assess_zone_probability
from qwen_backend.zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateProbabilityEvidence,
    ProbabilitySignal,
    ProbabilitySignalKind,
    ZoneBeliefInput,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
)

PolicyName: TypeAlias = Literal["static_representative", "posterior_only", "lr_hmm_eig"]
TargetState: TypeAlias = int | Literal["outside", "unknown"]
POLICIES: tuple[PolicyName, ...] = (
    "static_representative",
    "posterior_only",
    "lr_hmm_eig",
)
HASH_PLACEHOLDER = "0" * 64
MAX_SCANS = 8


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _operating_hash(point: OperatingPoint) -> str:
    payload = json.dumps(asdict(point), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _target_state(rng: random.Random, scenario: str) -> TargetState:
    sample = rng.random()
    if scenario in {"location_certain", "currently_inside"}:
        return rng.randint(1, 4)
    if scenario == "location_uncertain":
        if sample < 0.80:
            return rng.randint(1, 4)
        return "outside" if sample < 0.90 else "unknown"
    if sample < 0.20:
        return rng.randint(1, 4)
    return "outside" if sample < 0.70 else "unknown"


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
                        rng.uniform(0.62, 0.95)
                        if position == 1
                        else rng.uniform(0.35, 0.82)
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
            observed_at="2026-08-01T03:00:00Z",
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
        zone_count=4,
        candidate_prior_probability=0.10,
        advance_motion=False,
        previous_zone_posterior=zone_prior,
        previous_outside_probability=outside_prior,
        previous_unknown_probability=unknown_prior,
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
    if policy == "static_representative":
        return min(
            remaining,
            key=lambda camera: (camera.position, camera.zone_id, camera.camera_id),
        )
    if policy == "posterior_only":
        zone_probability = {item.zone_id: item.probability for item in response.zone_posterior}
        return max(
            remaining,
            key=lambda camera: (
                zone_probability[camera.zone_id] * camera.operational_factor,
                -camera.position,
                camera.camera_id,
            ),
        )
    next_camera_id = response.next_camera_id
    ranking_by_id = {item.camera_id: item for item in response.ranked_cameras}
    selected = max(
        remaining,
        key=lambda camera: (
            ranking_by_id[camera.camera_id].expected_information_gain
            * ranking_by_id[camera.camera_id].operational_factor,
            camera.camera_id == next_camera_id,
            camera.camera_id,
        ),
    )
    return selected


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


def _run_episode(
    *,
    episode_id: str,
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
        top_state, top_probability = _top_state(response)
        if isinstance(top_state, int) and top_state != target and top_probability >= 0.75:
            false_activation = True
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
            )
        )
        top_state, top_probability = _top_state(response)
        if top_state == target and top_probability >= 0.55 and resolved_at > MAX_SCANS:
            resolved_at = scan_index
    final_top_state, _ = _top_state(response)
    return EpisodeOutcome(
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


def _public_reid_evidence(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    test = payload["testMetrics"]
    return {
        "artifact": path.as_posix(),
        "sha256": _sha256(path),
        "dataset": "PRID2011 public cross-camera proxy",
        "sealedTestEvaluationCount": payload["sealedTestEvaluationCount"],
        "knownQueries": test["known_queries"],
        "distractorQueries": test["distractor_queries"],
        "knownRank1": test["known_rank1"],
        "knownRecallAt5": test["known_recall_at5"],
        "distractorFalseMatchRate": test["distractor_false_match_rate"],
        "automaticDecisionAccuracy": test["automatic_decision_accuracy"],
        "projectCctvEvidence": False,
    }


def _runtime_evidence() -> dict[str, object]:
    try:
        gpu_output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,driver_version,memory.total",
                "--format=csv,noheader",
            ],
            text=True,
            timeout=20,
        )
        gpus = [line.strip() for line in gpu_output.splitlines() if line.strip()]
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        gpus = []
    return {
        "hostname": platform.node(),
        "platform": platform.platform(),
        "python": platform.python_version(),
        "gpus": gpus,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Paired four-zone replay for static, posterior-only, and LR-HMM-EIG policies"
    )
    parser.add_argument("--episodes-per-cell", type=int, default=250)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--public-reid-result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes_per_cell < 50:
        raise ValueError("episodes-per-cell must be at least 50")

    public_evidence = _public_reid_evidence(args.public_reid_result)
    model_sha = str(public_evidence["sha256"])
    points = (
        OperatingPoint("validation_wilson_conservative", 0.84, 0.09, 0.10),
        OperatingPoint("degraded_camera", 0.70, 0.15, 0.20),
        OperatingPoint("occlusion_stress", 0.60, 0.18, 0.25),
    )
    scenarios = (
        "location_certain",
        "location_uncertain",
        "currently_inside",
        "recording_only_or_outside",
    )
    outcomes: list[EpisodeOutcome] = []
    for scenario_index, scenario in enumerate(scenarios):
        for point_index, point in enumerate(points):
            for episode_index in range(args.episodes_per_cell):
                cell_seed = (
                    args.seed
                    + (scenario_index * 1_000_000)
                    + (point_index * 100_000)
                    + episode_index
                )
                rng = random.Random(cell_seed)
                episode_id = f"{scenario}:{point.name}:{episode_index}"
                target = _target_state(rng, scenario)
                prior = _prior(rng, scenario, target)
                cameras = _cameras(rng, point)
                evidence = _candidate_evidence(
                    rng, episode_id, target, point, model_sha
                )
                draws = {camera.camera_id: rng.random() for camera in cameras}
                for policy in POLICIES:
                    outcomes.append(
                        _run_episode(
                            episode_id=episode_id,
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

    by_policy: defaultdict[PolicyName, list[EpisodeOutcome]] = defaultdict(list)
    by_cell: defaultdict[tuple[str, str, PolicyName], list[EpisodeOutcome]] = defaultdict(list)
    for outcome in outcomes:
        by_policy[outcome.policy].append(outcome)
        by_cell[(outcome.scenario, outcome.operating_point, outcome.policy)].append(outcome)
    aggregate = {policy: _round_metrics(_aggregate(by_policy[policy])) for policy in POLICIES}
    selected: PolicyName = min(
        POLICIES,
        key=lambda policy: (
            -float(aggregate[policy]["resolvedWithinBudgetRate"]),
            float(aggregate[policy]["falseZoneActivationRate"]),
            float(aggregate[policy]["meanScansToResolution"]),
        ),
    )
    result = {
        "schemaVersion": "eyesonu-zone-policy-replay-v1",
        "status": "valid",
        "seed": args.seed,
        "episodesPerCell": args.episodes_per_cell,
        "pairedEpisodeCount": len(scenarios) * len(points) * args.episodes_per_cell,
        "publicReidEvidence": public_evidence,
        "topologyReplayEvidence": {
            "kind": "deterministic Monte Carlo counterfactual proxy",
            "projectCctvEvidence": False,
            "synchronizedMultiCameraObservation": False,
            "scenarios": list(scenarios),
            "operatingPoints": [asdict(point) for point in points],
            "maxScans": MAX_SCANS,
            "aggregateByPolicy": aggregate,
            "byScenarioAndOperatingPoint": {
                f"{scenario}/{point.name}/{policy}": _round_metrics(
                    _aggregate(by_cell[(scenario, point.name, policy)])
                )
                for scenario in scenarios
                for point in points
                for policy in POLICIES
            },
        },
        "selectedPolicy": selected,
        "selectedRuntimePolicy": "lr_hmm_posterior_weighted_coverage_eig_tiebreak",
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
            "staleRevisionHandledByExistingOperatorDecisionEndpoint": True,
        },
        "runtimeEvidence": _runtime_evidence(),
        "promotionDecision": {
            "projectCctvGeneralization85Confirmed": False,
            "cameraUtilityCausalImprovementConfirmed": False,
            "reason": (
                "The public ReID artifact is a proxy and the four-zone topology replay is "
                "simulated; synchronized project-camera counterfactual observations are absent."
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"selectedPolicy": selected, "aggregate": aggregate}, sort_keys=True))


if __name__ == "__main__":
    main()
