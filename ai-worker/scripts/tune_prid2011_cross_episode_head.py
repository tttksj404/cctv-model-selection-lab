from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

import numpy as np

from scripts.prid2011_open_set_features import (
    OpenSetBatch,
    build_training_episodes,
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)
from scripts.prid2011_open_set_models import ProbabilityModel
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_cache_ensemble import candidate_models
from scripts.tune_prid2011_camera_invariant import (
    TransformSpec,
    apply_camera_transform,
    fit_camera_transform,
)


class CrossEpisodeHeadError(RuntimeError):
    pass


class HeadSelection(TypedDict):
    name: str
    threshold: float
    calibration_metrics: dict[str, int | float]
    validation_metrics: dict[str, int | float]
    calibration_feasible: bool
    validation_feasible: bool


def _labels(batch: OpenSetBatch) -> np.ndarray:
    return (batch.known & batch.top1_correct).astype(np.int32)


def fit_cross_episode_head(
    tracks: Sequence[TrackEmbedding],
    *,
    episodes: int,
    seed: int,
) -> tuple[str, ProbabilityModel, float, HeadSelection, list[HeadSelection]]:
    train_batch = build_training_episodes(tracks, episodes, seed)
    calibration_batch = build_training_episodes(
        tracks,
        episodes,
        seed + 1_000_003,
    )
    validation_batch = extract_open_set_batch(
        [track for track in tracks if track.split == "validation"]
    )
    train_labels = _labels(train_batch)
    rows: list[HeadSelection] = []
    best: tuple[
        tuple[float, ...],
        str,
        ProbabilityModel,
        float,
        HeadSelection,
    ] | None = None
    for name, model in candidate_models(seed).items():
        model.fit(train_batch.features, train_labels)
        calibration_probabilities = model.predict_proba(
            calibration_batch.features
        )[:, 1]
        threshold, calibration_metrics, calibration_feasible = select_threshold(
            calibration_batch,
            calibration_probabilities,
        )
        validation_probabilities = model.predict_proba(
            validation_batch.features
        )[:, 1]
        validation_metrics = decision_metrics(
            validation_batch,
            validation_probabilities >= threshold,
        )
        validation_feasible = (
            validation_metrics.distractor_false_match_rate <= 0.05
            and validation_metrics.false_reject_rate <= 0.15
            and validation_metrics.known_rank1 >= 0.85
            and validation_metrics.known_recall_at5 >= 0.95
        )
        row: HeadSelection = {
            "name": name,
            "threshold": threshold,
            "calibration_metrics": asdict(calibration_metrics),
            "validation_metrics": asdict(validation_metrics),
            "calibration_feasible": calibration_feasible,
            "validation_feasible": validation_feasible,
        }
        rows.append(row)
        key = (
            float(calibration_feasible and validation_feasible),
            min(
                calibration_metrics.automatic_decision_accuracy,
                validation_metrics.automatic_decision_accuracy,
            ),
            validation_metrics.automatic_decision_accuracy,
            calibration_metrics.automatic_decision_accuracy,
            -max(
                calibration_metrics.distractor_false_match_rate,
                validation_metrics.distractor_false_match_rate,
            ),
            -max(
                calibration_metrics.false_reject_rate,
                validation_metrics.false_reject_rate,
            ),
        )
        candidate = (key, name, model, threshold, row)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise CrossEpisodeHeadError("cross-episode head search produced no candidate")
    return best[1], best[2], best[3], best[4], rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fit an open-set verifier on synthetic train episodes, calibrate its "
            "threshold on independently generated train episodes, check validation, "
            "then evaluate the sealed test once"
        )
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    parser.add_argument("--camera-mean-alpha", type=float, default=0.0)
    parser.add_argument("--difference-rank", type=int, default=0)
    parser.add_argument("--difference-alpha", type=float, default=0.0)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tracks = load_track_cache(args.track_cache)
    spec = TransformSpec(
        name=(
            f"mean{args.camera_mean_alpha:.2f}-diff{args.difference_rank}"
            f"-alpha{args.difference_alpha:.2f}"
        ),
        camera_mean_alpha=args.camera_mean_alpha,
        difference_rank=args.difference_rank,
        difference_alpha=args.difference_alpha,
    )
    transform = fit_camera_transform(tracks, spec)
    transformed = apply_camera_transform(tracks, transform)
    name, model, threshold, selected, candidates = fit_cross_episode_head(
        transformed,
        episodes=args.episodes,
        seed=args.seed,
    )
    test_batch = extract_open_set_batch(
        [track for track in transformed if track.split == "test"]
    )
    probabilities = model.predict_proba(test_batch.features)[:, 1]
    test_metrics = decision_metrics(test_batch, probabilities >= threshold)
    result = {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "method": (
            "train-episode verifier with independent train-episode threshold "
            "calibration and validation confirmation"
        ),
        "selectionProtocol": (
            "head fitted on synthetic train episodes; threshold selected on a "
            "disjoint synthetic episode stream; head selected using calibration and "
            "validation identities; sealed test evaluated once"
        ),
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": False,
            "thresholdSelectedWithoutTest": True,
            "projectCctvEvidence": False,
        },
        "transform": asdict(spec),
        "selectedHead": selected,
        "candidateHeads": candidates,
        "testMetrics": asdict(test_metrics),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    metadata = {
        "schemaVersion": "prid2011-cross-episode-head-v1",
        "transform": asdict(spec),
        "openSetHead": name,
        "openSetThreshold": threshold,
        "openSetState": {
            state_name: value.tolist()
            for state_name, value in model.state().items()
        },
        "cameraNames": sorted(transform.camera_offsets),
    }
    camera_names = sorted(transform.camera_offsets)
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.head_output,
        metadata=np.asarray(json.dumps(metadata, sort_keys=True)),
        global_mean=transform.global_mean,
        difference_basis=transform.difference_basis,
        camera_offsets=np.stack(
            [transform.camera_offsets[camera] for camera in camera_names]
        ),
    )
    print(
        json.dumps(
            {
                "transform": asdict(spec),
                "selectedHead": selected,
                "testMetrics": asdict(test_metrics),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

