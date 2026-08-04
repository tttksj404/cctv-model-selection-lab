from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict
from itertools import combinations
from pathlib import Path
from typing import TypedDict

import numpy as np

from scripts.prid2011_open_set_features import (
    FEATURE_NAMES,
    OpenSetBatch,
    build_training_episodes,
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)
from scripts.prid2011_open_set_models import (
    LinearProbabilityHead,
    ProbabilityModel,
    TanhProbabilityHead,
)
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding


class CacheEnsembleError(RuntimeError):
    pass


class CandidateRow(TypedDict):
    name: str
    weights: dict[str, float]
    openSetHead: str
    threshold: float
    validationFeasible: bool
    validationMetrics: dict[str, int | float]


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise CacheEnsembleError("track cache contains a zero-norm vector")
    return np.asarray(vector / norm, dtype=np.float32)


def _track_map(tracks: Sequence[TrackEmbedding]) -> dict[str, TrackEmbedding]:
    mapped = {track.track_id: track for track in tracks}
    if len(mapped) != len(tracks):
        raise CacheEnsembleError("track cache contains duplicate track ids")
    return mapped


def fuse_track_caches(
    caches: Mapping[str, Sequence[TrackEmbedding]],
    weights: Mapping[str, float],
) -> list[TrackEmbedding]:
    if not weights or any(weight <= 0 for weight in weights.values()):
        raise CacheEnsembleError("ensemble weights must be positive")
    if set(weights) - set(caches):
        raise CacheEnsembleError("ensemble references an unavailable cache")
    total = float(sum(weights.values()))
    normalized_weights = {name: weight / total for name, weight in weights.items()}
    selected_maps = {name: _track_map(caches[name]) for name in normalized_weights}
    first_name = next(iter(normalized_weights))
    first_tracks = list(caches[first_name])
    expected_ids = {track.track_id for track in first_tracks}
    for name, mapped in selected_maps.items():
        if set(mapped) != expected_ids:
            raise CacheEnsembleError(f"track ids differ for cache {name}")

    fused: list[TrackEmbedding] = []
    for reference in first_tracks:
        parts: list[np.ndarray] = []
        for name, weight in normalized_weights.items():
            current = selected_maps[name][reference.track_id]
            metadata = (
                current.identity,
                current.role,
                current.camera,
                current.split,
                current.frame_count,
            )
            expected = (
                reference.identity,
                reference.role,
                reference.camera,
                reference.split,
                reference.frame_count,
            )
            if metadata != expected:
                raise CacheEnsembleError(
                    f"track metadata differs for {reference.track_id} in cache {name}"
                )
            parts.append(np.sqrt(weight) * _normalize(current.vector))
        fused.append(
            TrackEmbedding(
                track_id=reference.track_id,
                identity=reference.identity,
                role=reference.role,
                camera=reference.camera,
                split=reference.split,
                vector=_normalize(np.concatenate(parts)),
                frame_count=reference.frame_count,
            )
        )
    return fused


def candidate_models(seed: int) -> dict[str, ProbabilityModel]:
    return {
        "linear-l2-0.001": LinearProbabilityHead(regularization=0.001),
        "linear-l2-0.01": LinearProbabilityHead(regularization=0.01),
        "tanh-h16-l2-0.001": TanhProbabilityHead(
            hidden_size=16, regularization=0.001, seed=seed
        ),
        "tanh-h32-l2-0.01": TanhProbabilityHead(
            hidden_size=32, regularization=0.01, seed=seed + 1
        ),
    }


def fit_open_set_head(
    tracks: Sequence[TrackEmbedding], episodes: int, seed: int
) -> tuple[str, ProbabilityModel, float, dict[str, int | float], bool]:
    train_batch = build_training_episodes(tracks, episodes, seed)
    validation_batch = extract_open_set_batch(
        [track for track in tracks if track.split == "validation"]
    )
    train_labels = (train_batch.known & train_batch.top1_correct).astype(np.int32)
    best: (
        tuple[
            tuple[float, ...],
            str,
            ProbabilityModel,
            float,
            dict[str, int | float],
            bool,
        ]
        | None
    ) = None
    for name, model in candidate_models(seed).items():
        model.fit(train_batch.features, train_labels)
        probabilities = model.predict_proba(validation_batch.features)[:, 1]
        threshold, metrics, threshold_feasible = select_threshold(
            validation_batch, probabilities
        )
        feasible = (
            threshold_feasible
            and metrics.known_rank1 >= 0.85
            and metrics.known_recall_at5 >= 0.95
        )
        key = (
            float(feasible),
            metrics.automatic_decision_accuracy,
            metrics.known_rank1,
            -metrics.distractor_false_match_rate,
            -metrics.false_reject_rate,
        )
        candidate = (
            key,
            name,
            model,
            threshold,
            asdict(metrics),
            feasible,
        )
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise CacheEnsembleError("open-set head search produced no candidate")
    return best[1], best[2], best[3], best[4], best[5]


def _weight_candidates(names: set[str]) -> list[tuple[str, dict[str, float]]]:
    if "solider" not in names:
        raise CacheEnsembleError("SOLIDER cache is required")
    rows: list[tuple[str, dict[str, float]]] = [
        ("solider", {"solider": 1.0})
    ]
    secondary_names = sorted(names - {"solider"})
    for secondary in secondary_names:
        for secondary_weight in (0.10, 0.25, 0.50):
            solider_weight = 1.0 - secondary_weight
            rows.append(
                (
                    f"solider{solider_weight:.2f}-{secondary}{secondary_weight:.2f}",
                    {"solider": solider_weight, secondary: secondary_weight},
                )
            )
    for left, right in combinations(secondary_names, 2):
        for secondary_weight in (0.15, 0.25):
            solider_weight = 1.0 - (2.0 * secondary_weight)
            rows.append(
                (
                    f"solider{solider_weight:.2f}-{left}{secondary_weight:.2f}"
                    f"-{right}{secondary_weight:.2f}",
                    {
                        "solider": solider_weight,
                        left: secondary_weight,
                        right: secondary_weight,
                    },
                )
            )
    if len(secondary_names) >= 3:
        for total_secondary_weight in (0.30, 0.50):
            secondary_weight = total_secondary_weight / len(secondary_names)
            weights = {
                "solider": 1.0 - total_secondary_weight,
                **{name: secondary_weight for name in secondary_names},
            }
            rows.append(
                (
                    f"solider{1.0 - total_secondary_weight:.2f}-all"
                    f"{total_secondary_weight:.2f}",
                    weights,
                )
            )
    return rows


def _parse_cache(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("cache must use NAME=PATH")
    return name, Path(path)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select a score-equivalent multi-backbone track ensemble on PRID2011 "
            "validation identities and evaluate the sealed test once"
        )
    )
    parser.add_argument(
        "--cache",
        action="append",
        type=_parse_cache,
        required=True,
        metavar="NAME=PATH",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cache_paths = dict(args.cache)
    if len(cache_paths) != len(args.cache):
        raise CacheEnsembleError("cache names must be unique")
    caches = {
        name: load_track_cache(path) for name, path in cache_paths.items()
    }
    candidates: list[CandidateRow] = []
    best: (
        tuple[
            tuple[float, ...],
            str,
            dict[str, float],
            list[TrackEmbedding],
            ProbabilityModel,
            float,
            str,
        ]
        | None
    ) = None
    for index, (name, weights) in enumerate(_weight_candidates(set(caches))):
        fused = fuse_track_caches(caches, weights)
        (
            head_name,
            model,
            threshold,
            validation_metrics,
            feasible,
        ) = fit_open_set_head(fused, args.episodes, args.seed + index)
        key = (
            float(feasible),
            float(validation_metrics["automatic_decision_accuracy"]),
            float(validation_metrics["known_rank1"]),
            -float(validation_metrics["distractor_false_match_rate"]),
            -float(validation_metrics["false_reject_rate"]),
        )
        row: CandidateRow = {
            "name": name,
            "weights": weights,
            "openSetHead": head_name,
            "threshold": threshold,
            "validationFeasible": feasible,
            "validationMetrics": validation_metrics,
        }
        candidates.append(row)
        candidate = (key, name, weights, fused, model, threshold, head_name)
        if best is None or candidate[0] > best[0]:
            best = candidate
    if best is None:
        raise CacheEnsembleError("ensemble search produced no candidate")

    _, selected_name, selected_weights, fused, model, threshold, head_name = best
    test_batch: OpenSetBatch = extract_open_set_batch(
        [track for track in fused if track.split == "test"]
    )
    test_probabilities = model.predict_proba(test_batch.features)[:, 1]
    test_metrics = decision_metrics(test_batch, test_probabilities >= threshold)
    selected_row = next(row for row in candidates if row["name"] == selected_name)
    result = {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "method": "validation-selected multi-backbone score ensemble",
        "selectionProtocol": (
            "weights, open-set head, and threshold selected on validation identities; "
            "sealed test evaluated once after selection"
        ),
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": True,
            "projectCctvEvidence": False,
        },
        "cachePaths": {name: str(path) for name, path in cache_paths.items()},
        "featureNames": FEATURE_NAMES,
        "selected": selected_row,
        "candidates": candidates,
        "testMetrics": asdict(test_metrics),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    metadata = {
        "schemaVersion": "prid2011-cache-ensemble-v1",
        "weights": selected_weights,
        "openSetFeatureNames": FEATURE_NAMES,
        "openSetHead": head_name,
        "openSetThreshold": threshold,
        "openSetState": {
            name: value.tolist() for name, value in model.state().items()
        },
    }
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.head_output,
        metadata=np.asarray(json.dumps(metadata, sort_keys=True)),
    )
    print(
        json.dumps(
            {
                "selected": selected_row,
                "testMetrics": asdict(test_metrics),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
