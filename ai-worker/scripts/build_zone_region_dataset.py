from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter
from pathlib import Path
from typing import Literal, TypeAlias

import scripts.benchmark_zone_probability_policy as replay
from qwen_backend.zone_probability import assess_zone_probability
from qwen_backend.zone_probability_schemas import CameraObservationStatus, ZoneProbabilityResponse
from scripts.zone_policy_registry import OPERATING_POINT_VALUES, SCENARIOS
from scripts.zone_policy_replay_seed import target_state_from_rng
from scripts.zone_region_metrics import conditional_zone_probabilities

RouteName: TypeAlias = Literal[
    "representative_4",
    "deployed_runtime_8",
    "expected_bayes_8",
]
RoutePolicyName: TypeAlias = Literal[
    "static_representative",
    "deployed_runtime",
    "expected_bayes_accuracy",
]
ROUTES: tuple[RouteName, ...] = (
    "representative_4",
    "deployed_runtime_8",
    "expected_bayes_8",
)
FEATURE_NAMES = (
    *(f"initial_zone_{zone_id}" for zone_id in range(1, 5)),
    *(f"final_zone_{zone_id}" for zone_id in range(1, 5)),
    "outside_probability",
    "unknown_probability",
    "posterior_entropy",
    *(f"candidate_zone_{zone_id}" for zone_id in range(1, 5)),
    "candidate_probability",
    "candidate_track_quality",
    *(
        f"zone_{zone_id}_{name}"
        for zone_id in range(1, 5)
        for name in (
            "scan_count",
            "match_count",
            "no_match_count",
            "scanned_operational_mean",
            "available_fraction",
            "camera_operational_mean",
        )
    ),
    *(f"scenario_{scenario}" for scenario in SCENARIOS),
    *(f"operating_point_{name}" for name, *_ in OPERATING_POINT_VALUES),
)


def _route_configuration(route: RouteName) -> tuple[RoutePolicyName, int]:
    if route == "representative_4":
        return "static_representative", 4
    if route == "deployed_runtime_8":
        return "deployed_runtime", 8
    return "expected_bayes_accuracy", 8


def _run_route(
    *,
    episode_id: str,
    route: RouteName,
    target: int,
    cameras: tuple[replay.ReplayCamera, ...],
    evidence: tuple[replay.CandidateProbabilityEvidence, ...],
    prior: tuple[tuple[replay.ZoneBeliefInput, ...], float, float],
    draws: dict[str, float],
) -> tuple[ZoneProbabilityResponse, tuple[tuple[int, CameraObservationStatus, float], ...]]:
    policy, max_scans = _route_configuration(route)
    response = assess_zone_probability(
        replay.make_request(
            episode_id=episode_id,
            cameras=cameras,
            evidence=evidence,
            prior=prior,
        )
    )
    scanned: frozenset[str] = frozenset()
    observations: list[tuple[int, CameraObservationStatus, float]] = []
    for _ in range(max_scans):
        camera = replay.choose_camera(policy, response, cameras, scanned)
        if camera is None:
            break
        status = replay.observation_status(target, camera, draws[camera.camera_id])
        scanned = scanned | {camera.camera_id}
        observations.append((camera.zone_id, status, camera.operational_factor))
        response = assess_zone_probability(
            replay.make_request(
                episode_id=episode_id,
                cameras=cameras,
                evidence=(),
                prior=replay.response_prior(response),
                scanned=scanned,
                observed_camera_id=camera.camera_id,
                observed_status=status,
                previous_deduplication_state=response.deduplication_state,
            )
        )
    return response, tuple(observations)


def _feature_values(
    *,
    scenario: str,
    operating_point: str,
    prior: tuple[tuple[replay.ZoneBeliefInput, ...], float, float],
    cameras: tuple[replay.ReplayCamera, ...],
    evidence: tuple[replay.CandidateProbabilityEvidence, ...],
    response: ZoneProbabilityResponse,
    observations: tuple[tuple[int, CameraObservationStatus, float], ...],
) -> list[float]:
    initial = conditional_zone_probabilities(tuple(item.probability for item in prior[0]))
    final = conditional_zone_probabilities(
        tuple(item.probability for item in response.zone_posterior)
    )
    candidate_zone = evidence[0].zone_id if evidence else None
    candidate_probability = evidence[0].signals[0].probability if evidence else 0.0
    candidate_quality = evidence[0].track_quality if evidence else 0.0
    values: list[float] = [*initial, *final]
    values.extend(
        (response.outside_probability, response.unknown_probability, response.posterior_entropy)
    )
    values.extend(float(candidate_zone == zone_id) for zone_id in range(1, 5))
    values.extend((candidate_probability, candidate_quality))
    for zone_id in range(1, 5):
        zone_observations = tuple(item for item in observations if item[0] == zone_id)
        zone_cameras = tuple(camera for camera in cameras if camera.zone_id == zone_id)
        operational = tuple(item[2] for item in zone_observations)
        values.extend(
            (
                float(len(zone_observations)),
                float(sum(item[1] is CameraObservationStatus.MATCH for item in zone_observations)),
                float(
                    sum(
                        item[1] is CameraObservationStatus.NO_MATCH
                        for item in zone_observations
                    )
                ),
                sum(operational) / len(operational) if operational else 0.0,
                sum(camera.available for camera in zone_cameras) / len(zone_cameras),
                sum(camera.operational_factor for camera in zone_cameras) / len(zone_cameras),
            )
        )
    values.extend(float(scenario == name) for name in SCENARIOS)
    values.extend(float(operating_point == name) for name, *_ in OPERATING_POINT_VALUES)
    if len(values) != len(FEATURE_NAMES) or any(not math.isfinite(value) for value in values):
        raise RuntimeError("zone feature vector contract is invalid")
    return values


def write_dataset(path: Path, rows: list[dict[str, object]]) -> dict[str, object]:
    payload = (
        "\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n"
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    return {
        "uri": path.as_posix(),
        "rowCount": len(rows),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build four-zone selection and sealed datasets")
    parser.add_argument("--episodes-per-cell", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260801)
    parser.add_argument("--selection-output", type=Path, required=True)
    parser.add_argument("--sealed-output", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    if args.episodes_per_cell < 100:
        raise ValueError("episodes-per-cell must be at least 100")
    model_sha = hashlib.sha256(b"zone-region-dataset-source").hexdigest()
    points = tuple(replay.OperatingPoint(*values) for values in OPERATING_POINT_VALUES)
    rows: list[dict[str, object]] = []
    for cohort_index, cohort in enumerate(("selection", "sealed_test")):
        for scenario_index, scenario in enumerate(SCENARIOS):
            for point_index, point in enumerate(points):
                for episode_index in range(args.episodes_per_cell):
                    cell_seed = (
                        args.seed
                        + cohort_index * 10_000_000
                        + scenario_index * 1_000_000
                        + point_index * 100_000
                        + episode_index
                    )
                    rng = random.Random(cell_seed)
                    target = target_state_from_rng(rng, scenario)
                    prior = replay.make_prior(rng, scenario, target)
                    cameras = replay.make_cameras(rng, point)
                    episode_id = f"{cohort}:{scenario}:{point.name}:{episode_index}"
                    evidence = replay.make_candidate_evidence(
                        rng,
                        episode_id,
                        target,
                        point,
                        model_sha,
                    )
                    draws = {camera.camera_id: rng.random() for camera in cameras}
                    if not isinstance(target, int):
                        continue
                    for route in ROUTES:
                        response, observations = _run_route(
                            episode_id=episode_id,
                            route=route,
                            target=target,
                            cameras=cameras,
                            evidence=evidence,
                            prior=prior,
                            draws=draws,
                        )
                        rows.append(
                            {
                                "cohort": cohort,
                                "route": route,
                                "targetZone": target,
                                "features": _feature_values(
                                    scenario=scenario,
                                    operating_point=point.name,
                                    prior=prior,
                                    cameras=cameras,
                                    evidence=evidence,
                                    response=response,
                                    observations=observations,
                                ),
                            }
                        )
    datasets: dict[str, dict[str, object]] = {}
    for cohort, output in (
        ("selection", args.selection_output),
        ("sealed_test", args.sealed_output),
    ):
        cohort_rows = [row for row in rows if row["cohort"] == cohort]
        datasets[cohort] = write_dataset(output, cohort_rows)
    counts = Counter((str(row["cohort"]), str(row["route"])) for row in rows)
    feature_schema_payload = json.dumps(FEATURE_NAMES, separators=(",", ":")).encode("utf-8")
    manifest = {
        "schemaVersion": "eyesonu-zone-region-dataset-v2",
        "seed": args.seed,
        "episodesPerCell": args.episodes_per_cell,
        "featureNames": FEATURE_NAMES,
        "featureSchemaSha256": hashlib.sha256(feature_schema_payload).hexdigest(),
        "forbiddenModelInputs": ["cohort", "route", "targetZone", "cellSeed", "episodeId"],
        "rowCount": len(rows),
        "datasets": datasets,
        "rowsByCohortAndRoute": {
            f"{key[0]}:{key[1]}": value for key, value in sorted(counts.items())
        },
    }
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_bytes(
        json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8")
    )


if __name__ == "__main__":
    main()

