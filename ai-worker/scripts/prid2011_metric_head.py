from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, replace

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding


@dataclass(frozen=True, slots=True)
class MetricHead:
    mean: np.ndarray
    basis: np.ndarray
    projection: np.ndarray
    alpha: float
    regularization: float
    dimension: int


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return np.asarray(vectors / np.maximum(norms, 1e-12), dtype=np.float32)


def _camera_pairs(
    tracks: Sequence[TrackEmbedding],
) -> tuple[np.ndarray, np.ndarray]:
    grouped: dict[str, dict[str, np.ndarray]] = defaultdict(dict)
    for track in tracks:
        if track.split == "train":
            grouped[track.identity][track.camera] = track.vector
    camera_a: list[np.ndarray] = []
    camera_b: list[np.ndarray] = []
    for identity in sorted(grouped):
        cameras = grouped[identity]
        if "cam_a" in cameras and "cam_b" in cameras:
            camera_a.append(cameras["cam_a"])
            camera_b.append(cameras["cam_b"])
    if len(camera_a) < 10:
        raise ValueError("metric head requires at least 10 cross-camera train identities")
    return np.stack(camera_a), np.stack(camera_b)


def fit_kissme_head(
    tracks: Sequence[TrackEmbedding],
    regularization: float,
    dimension: int,
) -> MetricHead:
    if regularization <= 0.0:
        raise ValueError("regularization must be positive")
    camera_a, camera_b = _camera_pairs(tracks)
    samples = np.concatenate((camera_a, camera_b), axis=0)
    mean = np.mean(samples, axis=0)
    centered = samples - mean
    _, _, right = np.linalg.svd(centered, full_matrices=False)
    pca_dimension = min(128, len(samples) - 1, samples.shape[1])
    basis = right[:pca_dimension].T
    projected_a = (camera_a - mean) @ basis
    projected_b = (camera_b - mean) @ basis

    positive = projected_a - projected_b
    negative = np.stack(
        [
            projected_a[left] - projected_b[right_index]
            for left in range(len(projected_a))
            for right_index in range(len(projected_b))
            if left != right_index
        ]
    )
    positive_covariance = positive.T @ positive / len(positive)
    negative_covariance = negative.T @ negative / len(negative)
    identity = np.eye(pca_dimension, dtype=np.float64)
    metric = np.linalg.pinv(positive_covariance + regularization * identity)
    metric -= np.linalg.pinv(negative_covariance + regularization * identity)
    metric = (metric + metric.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(metric)
    positive_indices = np.flatnonzero(eigenvalues > 1e-9)
    if len(positive_indices) == 0:
        raise ValueError("KISSME metric has no positive eigenvalues")
    ordered = positive_indices[np.argsort(eigenvalues[positive_indices])[::-1]]
    selected = ordered[: min(dimension, len(ordered))]
    projection = eigenvectors[:, selected] * np.sqrt(eigenvalues[selected])
    return MetricHead(
        mean=np.asarray(mean, dtype=np.float32),
        basis=np.asarray(basis, dtype=np.float32),
        projection=np.asarray(projection, dtype=np.float32),
        alpha=1.0,
        regularization=regularization,
        dimension=len(selected),
    )


def with_alpha(head: MetricHead, alpha: float) -> MetricHead:
    if not 0.0 <= alpha <= 1.0:
        raise ValueError("alpha must be between zero and one")
    return replace(head, alpha=alpha)


def apply_metric_head(
    tracks: Sequence[TrackEmbedding],
    head: MetricHead,
) -> list[TrackEmbedding]:
    source = np.stack([track.vector for track in tracks])
    metric_vectors = _normalize_rows(
        (source - head.mean) @ head.basis @ head.projection
    )
    source = _normalize_rows(source)
    combined = _normalize_rows(
        np.concatenate(
            (
                np.sqrt(1.0 - head.alpha) * source,
                np.sqrt(head.alpha) * metric_vectors,
            ),
            axis=1,
        )
    )
    return [
        replace(track, vector=combined[index])
        for index, track in enumerate(tracks)
    ]

