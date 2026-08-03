from __future__ import annotations

import argparse
import json
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TypedDict

import numpy as np

from scripts.prid2011_open_set_features import (
    OpenSetBatch,
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_cache_ensemble import fit_open_set_head


class CameraInvariantError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TransformSpec:
    name: str
    camera_mean_alpha: float
    difference_rank: int
    difference_alpha: float


@dataclass(frozen=True, slots=True)
class FittedTransform:
    spec: TransformSpec
    global_mean: np.ndarray
    camera_offsets: dict[str, np.ndarray]
    difference_basis: np.ndarray


class CrossValidationRow(TypedDict):
    name: str
    spec: dict[str, int | float | str]
    metrics: dict[str, int | float]
    feasible: bool


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0:
        raise CameraInvariantError("track cache contains a zero-norm vector")
    return np.asarray(vector / norm, dtype=np.float32)


def fit_camera_transform(
    tracks: Sequence[TrackEmbedding], spec: TransformSpec
) -> FittedTransform:
    train_tracks = [track for track in tracks if track.split == "train"]
    if not train_tracks:
        raise CameraInvariantError("camera transform requires train tracks")
    vectors = np.stack([_normalize(track.vector) for track in train_tracks])
    global_mean = np.asarray(vectors.mean(axis=0), dtype=np.float32)
    by_camera: dict[str, list[np.ndarray]] = defaultdict(list)
    by_identity: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    for track, vector in zip(train_tracks, vectors, strict=True):
        by_camera[track.camera].append(vector)
        by_identity[track.identity][track.camera] = vector
    camera_offsets = {
        camera: np.asarray(np.mean(rows, axis=0) - global_mean, dtype=np.float32)
        for camera, rows in by_camera.items()
    }
    differences: list[np.ndarray] = []
    for rows in by_identity.values():
        if len(rows) < 2:
            continue
        first, second = [rows[camera] for camera in sorted(rows)[:2]]
        first = _normalize(
            first - spec.camera_mean_alpha * camera_offsets[sorted(rows)[0]]
        )
        second = _normalize(
            second - spec.camera_mean_alpha * camera_offsets[sorted(rows)[1]]
        )
        differences.append(first - second)
    if len(differences) < 20:
        raise CameraInvariantError(
            "camera transform requires at least 20 paired train identities"
        )
    if spec.difference_rank:
        _, _, right = np.linalg.svd(np.stack(differences), full_matrices=False)
        basis = np.asarray(
            right[: min(spec.difference_rank, len(right))], dtype=np.float32
        )
    else:
        basis = np.empty((0, vectors.shape[1]), dtype=np.float32)
    return FittedTransform(
        spec=spec,
        global_mean=global_mean,
        camera_offsets=camera_offsets,
        difference_basis=basis,
    )


def apply_camera_transform(
    tracks: Sequence[TrackEmbedding], transform: FittedTransform
) -> list[TrackEmbedding]:
    transformed: list[TrackEmbedding] = []
    for track in tracks:
        vector = _normalize(track.vector)
        offset = transform.camera_offsets.get(
            track.camera, np.zeros_like(transform.global_mean)
        )
        vector = _normalize(
            vector - transform.spec.camera_mean_alpha * offset
        )
        if len(transform.difference_basis):
            nuisance = (
                vector @ transform.difference_basis.T
            ) @ transform.difference_basis
            vector = _normalize(
                vector - transform.spec.difference_alpha * nuisance
            )
        transformed.append(
            TrackEmbedding(
                track_id=track.track_id,
                identity=track.identity,
                role=track.role,
                camera=track.camera,
                split=track.split,
                vector=vector,
                frame_count=track.frame_count,
            )
        )
    return transformed


def _fold_batch(
    tracks: Sequence[TrackEmbedding], fold_index: int
) -> OpenSetBatch:
    by_identity: dict[str, dict[str, TrackEmbedding]] = defaultdict(dict)
    for track in tracks:
        by_identity[track.identity][track.camera] = track
    paired = {
        identity: rows for identity, rows in by_identity.items() if len(rows) >= 2
    }
    identities = sorted(paired)
    if len(identities) < 12:
        raise CameraInvariantError("cross-validation fold has too few identities")
    unknown_count = max(2, len(identities) // 4)
    unknown = set(
        identities[
            fold_index % len(identities) : fold_index % len(identities)
            + unknown_count
        ]
    )
    if len(unknown) < unknown_count:
        unknown.update(identities[: unknown_count - len(unknown)])
    cameras = sorted(next(iter(paired.values())))
    gallery_camera, query_camera = (
        (cameras[0], cameras[1]) if fold_index % 2 == 0 else (cameras[1], cameras[0])
    )
    episode: list[TrackEmbedding] = []
    for identity in identities:
        rows = paired[identity]
        if identity not in unknown:
            gallery = rows[gallery_camera]
            episode.append(
                TrackEmbedding(
                    track_id=f"cv-{fold_index}-g-{gallery.track_id}",
                    identity=identity,
                    role="gallery",
                    camera=gallery.camera,
                    split="cross-validation",
                    vector=gallery.vector,
                    frame_count=gallery.frame_count,
                )
            )
        query = rows[query_camera]
        episode.append(
            TrackEmbedding(
                track_id=f"cv-{fold_index}-q-{query.track_id}",
                identity=identity,
                role="query",
                camera=query.camera,
                split="cross-validation",
                vector=query.vector,
                frame_count=query.frame_count,
            )
        )
    return extract_open_set_batch(episode)


def _concat_batches(batches: Sequence[OpenSetBatch]) -> OpenSetBatch:
    return OpenSetBatch(
        features=np.concatenate([batch.features for batch in batches]),
        known=np.concatenate([batch.known for batch in batches]),
        top1_correct=np.concatenate([batch.top1_correct for batch in batches]),
        correct_ranks=np.concatenate([batch.correct_ranks for batch in batches]),
    )


def _cross_validate(
    tracks: Sequence[TrackEmbedding],
    spec: TransformSpec,
    folds: int,
) -> tuple[dict[str, int | float], bool]:
    train_identities = sorted(
        {track.identity for track in tracks if track.split == "train"}
    )
    batches: list[OpenSetBatch] = []
    for fold_index in range(folds):
        heldout = {
            identity
            for index, identity in enumerate(train_identities)
            if index % folds == fold_index
        }
        fit_tracks = [
            track
            for track in tracks
            if track.split == "train" and track.identity not in heldout
        ]
        fold_tracks = [
            track
            for track in tracks
            if track.split == "train" and track.identity in heldout
        ]
        transform = fit_camera_transform(fit_tracks, spec)
        batches.append(
            _fold_batch(apply_camera_transform(fold_tracks, transform), fold_index)
        )
    combined = _concat_batches(batches)
    top_scores = np.clip((combined.features[:, 0] + 1.0) / 2.0, 0.0, 1.0)
    _, metrics, feasible = select_threshold(combined, top_scores)
    return asdict(metrics), feasible


def _specs() -> list[TransformSpec]:
    rows = [TransformSpec("identity-solider", 0.0, 0, 0.0)]
    rows.extend(
        TransformSpec(f"camera-mean-{alpha:.2f}", alpha, 0, 0.0)
        for alpha in (0.25, 0.50, 0.75, 1.0)
    )
    rows.extend(
        TransformSpec(
            f"diff-rank{rank}-alpha{alpha:.2f}",
            0.0,
            rank,
            alpha,
        )
        for rank in (4, 8, 16, 32, 64)
        for alpha in (0.25, 0.50, 0.75, 1.0)
    )
    rows.extend(
        TransformSpec(
            f"mean{mean_alpha:.2f}-diff{rank}-alpha{diff_alpha:.2f}",
            mean_alpha,
            rank,
            diff_alpha,
        )
        for mean_alpha in (0.50, 1.0)
        for rank in (8, 16, 32)
        for diff_alpha in (0.50, 1.0)
    )
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select camera-mean and paired-difference nuisance removal by train-only "
            "identity folds, then calibrate on validation and evaluate sealed test once"
        )
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    tracks = load_track_cache(args.track_cache)
    rows: list[CrossValidationRow] = []
    best: tuple[tuple[float, ...], TransformSpec] | None = None
    for spec in _specs():
        metrics, feasible = _cross_validate(tracks, spec, args.folds)
        key = (
            float(feasible),
            float(metrics["automatic_decision_accuracy"]),
            float(metrics["known_rank1"]),
            -float(metrics["distractor_false_match_rate"]),
            -float(metrics["false_reject_rate"]),
        )
        rows.append(
            {
                "name": spec.name,
                "spec": asdict(spec),
                "metrics": metrics,
                "feasible": feasible,
            }
        )
        if best is None or key > best[0]:
            best = (key, spec)
    if best is None:
        raise CameraInvariantError("camera-invariant search produced no candidate")

    selected_spec = best[1]
    transform = fit_camera_transform(tracks, selected_spec)
    transformed = apply_camera_transform(tracks, transform)
    (
        head_name,
        model,
        threshold,
        validation_metrics,
        validation_feasible,
    ) = fit_open_set_head(transformed, args.episodes, args.seed)
    test_batch = extract_open_set_batch(
        [track for track in transformed if track.split == "test"]
    )
    probabilities = model.predict_proba(test_batch.features)[:, 1]
    test_metrics = decision_metrics(test_batch, probabilities >= threshold)
    result = {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "method": "train-fold-selected camera nuisance removal plus open-set verifier",
        "selectionProtocol": (
            "camera transform selected by five identity-disjoint train folds; "
            "open-set head and threshold selected on validation identities; "
            "sealed test evaluated once"
        ),
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": True,
            "projectCctvEvidence": False,
        },
        "selectedTransform": asdict(selected_spec),
        "crossValidationCandidates": rows,
        "openSetHead": head_name,
        "openSetThreshold": threshold,
        "validationFeasible": validation_feasible,
        "validationMetrics": validation_metrics,
        "testMetrics": asdict(test_metrics),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    metadata = {
        "schemaVersion": "prid2011-camera-invariant-v1",
        "transform": asdict(selected_spec),
        "cameraNames": sorted(transform.camera_offsets),
        "openSetHead": head_name,
        "openSetThreshold": threshold,
        "openSetState": {
            name: value.tolist() for name, value in model.state().items()
        },
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
                "selectedTransform": asdict(selected_spec),
                "crossValidationMetrics": next(
                    row["metrics"] for row in rows if row["name"] == selected_spec.name
                ),
                "validationMetrics": validation_metrics,
                "testMetrics": asdict(test_metrics),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
