from __future__ import annotations

import argparse
import json
import math
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch

from scripts.prid2011_open_set_features import (
    DecisionMetrics,
    OpenSetBatch,
    decision_metrics,
)
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_gallery_aware_open_set import (
    apply_camera_invariant_head,
)


class GraphOpenSetError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class GraphBatch:
    open_set: OpenSetBatch
    confidences: dict[str, np.ndarray]


@dataclass(frozen=True, slots=True)
class SelectedCandidate:
    matrix_name: str
    confidence_name: str
    threshold: float
    validation_metrics: DecisionMetrics
    feasible: bool


def wilson_interval(
    successes: int,
    total: int,
    *,
    z_value: float = 1.959963984540054,
) -> dict[str, float | int]:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("Wilson interval counts are invalid")
    rate = successes / total
    denominator = 1.0 + z_value**2 / total
    center = (rate + z_value**2 / (2.0 * total)) / denominator
    radius = (
        z_value
        * math.sqrt(
            rate * (1.0 - rate) / total
            + z_value**2 / (4.0 * total**2)
        )
        / denominator
    )
    return {
        "successes": successes,
        "total": total,
        "rate": rate,
        "lower": center - radius,
        "upper": center + radius,
    }


def metric_wilson95(metrics: DecisionMetrics) -> dict[str, dict[str, float | int]]:
    known = metrics.known_queries
    distractors = metrics.distractor_queries
    total = metrics.query_tracks
    return {
        "knownRank1": wilson_interval(round(metrics.known_rank1 * known), known),
        "knownRecallAt5": wilson_interval(
            round(metrics.known_recall_at5 * known),
            known,
        ),
        "distractorFalseMatchRate": wilson_interval(
            round(metrics.distractor_false_match_rate * distractors),
            distractors,
        ),
        "falseRejectRate": wilson_interval(
            round(metrics.false_reject_rate * known),
            known,
        ),
        "automaticDecisionAccuracy": wilson_interval(
            round(metrics.automatic_decision_accuracy * total),
            total,
        ),
    }


def _normalize_rows(matrix: np.ndarray) -> np.ndarray:
    precise = np.asarray(matrix, dtype=np.float64)
    norms = np.linalg.norm(precise, axis=1, keepdims=True)
    if np.any(norms <= 0.0):
        raise GraphOpenSetError("embedding matrix contains a zero vector")
    return np.asarray(precise / norms, dtype=np.float64)


def _stable_order(values: np.ndarray, *, descending: bool = False) -> np.ndarray:
    quantized = _quantize(values)
    return np.argsort(
        -quantized if descending else quantized,
        kind="stable",
    )


def _quantize(values: np.ndarray) -> np.ndarray:
    precise = np.asarray(values, dtype=np.float64)
    return np.asarray(precise.round(decimals=12), dtype=np.float64)


def _split(
    tracks: Sequence[TrackEmbedding], split: str
) -> tuple[list[TrackEmbedding], list[TrackEmbedding]]:
    rows = [track for track in tracks if track.split == split]
    queries = [track for track in rows if track.role == "query"]
    gallery = [track for track in rows if track.role == "gallery"]
    if len(queries) < 2 or len(gallery) < 2:
        raise GraphOpenSetError(f"{split} requires query and gallery tracks")
    return queries, gallery


def cosine_matrix(
    queries: Sequence[TrackEmbedding],
    gallery: Sequence[TrackEmbedding],
) -> np.ndarray:
    query_matrix = _normalize_rows(np.stack([track.vector for track in queries]))
    gallery_matrix = _normalize_rows(np.stack([track.vector for track in gallery]))
    return _quantize(query_matrix @ gallery_matrix.T)


def csls_matrix(similarities: np.ndarray, neighbors: int) -> np.ndarray:
    width = min(neighbors, similarities.shape[1])
    height = min(neighbors, similarities.shape[0])
    query_density = np.mean(
        np.partition(similarities, -width, axis=1)[:, -width:],
        axis=1,
    )
    gallery_density = np.mean(
        np.partition(similarities, -height, axis=0)[-height:, :],
        axis=0,
    )
    return _quantize(
        2.0 * similarities - query_density[:, None] - gallery_density[None, :],
    )


def sinkhorn_matrix(
    similarities: np.ndarray,
    *,
    temperature: float,
    iterations: int = 80,
) -> np.ndarray:
    if temperature <= 0.0:
        raise ValueError("temperature must be positive")
    logits = similarities / temperature
    logits -= np.max(logits, axis=1, keepdims=True)
    transport = np.exp(logits, dtype=np.float64)
    column_mass = similarities.shape[0] / similarities.shape[1]
    for _ in range(iterations):
        transport /= np.maximum(np.sum(transport, axis=1, keepdims=True), 1e-12)
        transport *= column_mass / np.maximum(
            np.sum(transport, axis=0, keepdims=True),
            1e-12,
        )
    transport /= np.maximum(np.sum(transport, axis=1, keepdims=True), 1e-12)
    return _quantize(transport)


def k_reciprocal_matrix(
    queries: Sequence[TrackEmbedding],
    gallery: Sequence[TrackEmbedding],
    *,
    k1: int,
    k2: int,
    lambda_value: float,
) -> np.ndarray:
    if not 0.0 <= lambda_value <= 1.0:
        raise ValueError("lambda_value must be between zero and one")
    query_vectors = _normalize_rows(np.stack([track.vector for track in queries]))
    gallery_vectors = _normalize_rows(np.stack([track.vector for track in gallery]))
    vectors = np.concatenate((query_vectors, gallery_vectors))
    distance = np.maximum(0.0, 2.0 - 2.0 * (vectors @ vectors.T))
    distance = _quantize(
        (distance / np.maximum(np.max(distance, axis=0, keepdims=True), 1e-12)).T,
    )
    total = len(vectors)
    k1 = min(k1, total - 1)
    k2 = min(k2, total)
    initial_rank = np.vstack([_stable_order(row) for row in distance])
    weights = np.zeros_like(distance, dtype=np.float64)
    half_k = max(1, round(k1 / 2))
    for index in range(total):
        forward = initial_rank[index, : k1 + 1]
        backward = initial_rank[forward, : k1 + 1]
        reciprocal = forward[np.any(backward == index, axis=1)]
        expanded = reciprocal.copy()
        for candidate in reciprocal:
            candidate_forward = initial_rank[candidate, : half_k + 1]
            candidate_backward = initial_rank[candidate_forward, : half_k + 1]
            candidate_reciprocal = candidate_forward[
                np.any(candidate_backward == candidate, axis=1)
            ]
            overlap = len(np.intersect1d(candidate_reciprocal, reciprocal))
            if overlap > 2.0 / 3.0 * len(candidate_reciprocal):
                expanded = np.append(expanded, candidate_reciprocal)
        expanded = np.unique(expanded)
        affinity = np.exp(-distance[index, expanded])
        weights[index, expanded] = affinity / np.maximum(np.sum(affinity), 1e-12)
    if k2 > 1:
        expanded_weights = np.zeros_like(weights)
        for index in range(total):
            expanded_weights[index] = np.mean(
                weights[initial_rank[index, :k2]],
                axis=0,
            )
        weights = expanded_weights
    inverted = [np.flatnonzero(weights[:, index]) for index in range(total)]
    query_count = len(queries)
    jaccard = np.ones((query_count, total), dtype=np.float64)
    for query_index in range(query_count):
        nonzero = np.flatnonzero(weights[query_index])
        minimum = np.zeros(total, dtype=np.float64)
        for neighbor in nonzero:
            related = inverted[int(neighbor)]
            minimum[related] += np.minimum(
                weights[query_index, neighbor],
                weights[related, neighbor],
            )
        jaccard[query_index] -= minimum / np.maximum(2.0 - minimum, 1e-12)
    final_distance = (
        (1.0 - lambda_value) * jaccard[:, query_count:]
        + lambda_value * distance[:query_count, query_count:]
    )
    return _quantize(-final_distance)


def _robust_z(values: np.ndarray) -> float:
    if len(values) < 4:
        return 0.0
    median = float(np.median(values))
    mad = float(np.median(np.abs(values - median)))
    return float((values[0] - median) / max(1.4826 * mad, 1e-6))


def graph_batch(
    matrix: np.ndarray,
    queries: Sequence[TrackEmbedding],
    gallery: Sequence[TrackEmbedding],
) -> GraphBatch:
    if matrix.shape != (len(queries), len(gallery)):
        raise ValueError("similarity matrix shape does not match tracks")
    gallery_identities = {track.identity for track in gallery}
    known: list[bool] = []
    top1_correct: list[bool] = []
    correct_ranks: list[int] = []
    top_score: list[float] = []
    margin: list[float] = []
    row_z: list[float] = []
    robust_z: list[float] = []
    reciprocal: list[float] = []
    mutual: list[float] = []
    reverse_gap: list[float] = []
    joint_gap: list[float] = []
    for query_index, query in enumerate(queries):
        order = _stable_order(matrix[query_index], descending=True)
        ranked = matrix[query_index, order]
        gallery_index = int(order[0])
        ranked_identities = [gallery[int(index)].identity for index in order]
        is_known = query.identity in gallery_identities
        correct_rank = (
            ranked_identities.index(query.identity) + 1 if is_known else 0
        )
        reverse_order = _stable_order(
            matrix[:, gallery_index],
            descending=True,
        )
        reverse_values = matrix[reverse_order, gallery_index]
        reverse_rank = int(np.flatnonzero(reverse_order == query_index)[0]) + 1
        row_tail = ranked[1:]
        row_mean = sum(float(value) for value in row_tail) / len(row_tail)
        row_gap = float(ranked[0] - ranked[1])
        column_gap = float(reverse_values[0] - reverse_values[1])
        known.append(is_known)
        top1_correct.append(correct_rank == 1)
        correct_ranks.append(correct_rank)
        top_score.append(float(ranked[0]))
        margin.append(row_gap)
        row_z.append(
            (
                float(ranked[0]) - row_mean
            )
            / max(
                float(np.std(row_tail)),
                1e-6,
            )
        )
        robust_z.append(_robust_z(ranked))
        reciprocal.append(1.0 / reverse_rank)
        mutual.append(float(reverse_rank == 1))
        reverse_gap.append(column_gap)
        joint_gap.append(row_gap + max(column_gap, 0.0))
    open_set = OpenSetBatch(
        features=np.column_stack((top_score, margin)).astype(np.float32),
        known=np.asarray(known, dtype=np.bool_),
        top1_correct=np.asarray(top1_correct, dtype=np.bool_),
        correct_ranks=np.asarray(correct_ranks, dtype=np.int32),
    )
    confidences = {
        "top-score": np.asarray(top_score, dtype=np.float32),
        "margin": np.asarray(margin, dtype=np.float32),
        "row-z": np.asarray(row_z, dtype=np.float32),
        "robust-z": np.asarray(robust_z, dtype=np.float32),
        "reciprocal": np.asarray(reciprocal, dtype=np.float32),
        "mutual-row-z": np.asarray(row_z, dtype=np.float32)
        + np.asarray(mutual, dtype=np.float32),
        "joint-gap": np.asarray(joint_gap, dtype=np.float32),
        "graph-confidence": (
            np.asarray(row_z, dtype=np.float32)
            + np.asarray(reciprocal, dtype=np.float32)
            + np.asarray(mutual, dtype=np.float32)
            + np.asarray(reverse_gap, dtype=np.float32)
        ),
    }
    return GraphBatch(open_set=open_set, confidences=confidences)


def select_generic_threshold(
    batch: OpenSetBatch,
    confidence: np.ndarray,
) -> tuple[float, DecisionMetrics, bool]:
    unique = np.unique(confidence)
    if len(unique) > 256:
        unique = np.quantile(unique, np.linspace(0.0, 1.0, 256))
    thresholds = np.concatenate(
        (
            np.asarray([float(np.min(unique)) - 1e-6]),
            (unique[:-1] + unique[1:]) / 2.0,
            np.asarray([float(np.max(unique)) + 1e-6]),
        )
    )
    best: tuple[tuple[float, ...], float, DecisionMetrics, bool] | None = None
    for threshold in thresholds:
        metrics = decision_metrics(batch, confidence >= threshold)
        feasible = (
            metrics.distractor_false_match_rate <= 0.05
            and metrics.false_reject_rate <= 0.15
        )
        key = (
            float(feasible),
            metrics.automatic_decision_accuracy,
            metrics.known_rank1,
            -metrics.distractor_false_match_rate,
            -metrics.false_reject_rate,
        )
        if best is None or key > best[0]:
            best = (key, float(threshold), metrics, feasible)
    if best is None:
        raise GraphOpenSetError("threshold selection produced no candidate")
    return best[1], best[2], best[3]


def matrix_candidates(
    queries: Sequence[TrackEmbedding],
    gallery: Sequence[TrackEmbedding],
) -> dict[str, np.ndarray]:
    cosine = cosine_matrix(queries, gallery)
    candidates = {
        "cosine": cosine,
        "csls-5": csls_matrix(cosine, 5),
        "csls-10": csls_matrix(cosine, 10),
        "sinkhorn-001": sinkhorn_matrix(cosine, temperature=0.01),
        "sinkhorn-002": sinkhorn_matrix(cosine, temperature=0.02),
        "sinkhorn-003": sinkhorn_matrix(cosine, temperature=0.03),
    }
    for k1, k2, lambda_value in (
        (10, 4, 0.3),
        (20, 6, 0.3),
        (30, 6, 0.3),
        (20, 6, 0.5),
    ):
        candidates[f"krecip-{k1}-{k2}-{lambda_value:.1f}"] = k_reciprocal_matrix(
            queries,
            gallery,
            k1=k1,
            k2=k2,
            lambda_value=lambda_value,
        )
    return candidates


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Select graph re-ranking and open-set confidence on validation identities, "
            "then evaluate the unchanged test identity split."
        )
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--camera-invariant-head", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset-label", default="public ReID held-out partition")
    parser.add_argument("--protocol-label", default="custom query/gallery protocol")
    parser.add_argument("--allow-cpu", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    cuda_available = torch.cuda.is_available() and torch.cuda.device_count() > 0
    if not cuda_available and not args.allow_cpu:
        raise GraphOpenSetError("CUDA GPU is required unless --allow-cpu is set")
    raw_tracks = load_track_cache(
        args.track_cache,
        validate_public_protocol=True,
    )
    if args.camera_invariant_head is None:
        tracks = raw_tracks
        camera_metadata: dict[str, object] = {"applied": False}
    else:
        tracks, camera_metadata = apply_camera_invariant_head(
            raw_tracks,
            args.camera_invariant_head,
        )
        camera_metadata = {"applied": True, **camera_metadata}
    validation_queries, validation_gallery = _split(tracks, "validation")
    test_queries, test_gallery = _split(tracks, "test")
    validation_matrices = matrix_candidates(
        validation_queries,
        validation_gallery,
    )
    candidate_rows: list[dict[str, object]] = []
    selected: SelectedCandidate | None = None
    selected_key: tuple[float, ...] | None = None
    for matrix_name, matrix in validation_matrices.items():
        batch = graph_batch(matrix, validation_queries, validation_gallery)
        for confidence_name, confidence in batch.confidences.items():
            threshold, metrics, feasible = select_generic_threshold(
                batch.open_set,
                confidence,
            )
            candidate_rows.append(
                {
                    "matrix": matrix_name,
                    "confidence": confidence_name,
                    "threshold": threshold,
                    "feasible": feasible,
                    "validationMetrics": asdict(metrics),
                }
            )
            key = (
                float(feasible),
                metrics.automatic_decision_accuracy,
                metrics.known_rank1,
                -metrics.distractor_false_match_rate,
                -metrics.false_reject_rate,
                -float(matrix_name.startswith("cosine")),
            )
            if selected_key is None or key > selected_key:
                selected_key = key
                selected = SelectedCandidate(
                    matrix_name=matrix_name,
                    confidence_name=confidence_name,
                    threshold=threshold,
                    validation_metrics=metrics,
                    feasible=feasible,
                )
    if selected is None:
        raise GraphOpenSetError("graph candidate selection failed")
    test_matrix = matrix_candidates(test_queries, test_gallery)[
        selected.matrix_name
    ]
    test_batch = graph_batch(test_matrix, test_queries, test_gallery)
    test_confidence = test_batch.confidences[selected.confidence_name]
    fixed_test_metrics = decision_metrics(
        test_batch.open_set,
        test_confidence >= selected.threshold,
    )
    test_feasible = (
        fixed_test_metrics.distractor_false_match_rate <= 0.05
        and fixed_test_metrics.false_reject_rate <= 0.15
    )
    payload = {
        "schemaVersion": "eyesonu-prid2011-graph-open-set-v1",
        "status": (
            "exploratory-valid"
            if selected.feasible and test_feasible
            else "exploratory-infeasible"
        ),
        "device": {
            "type": "cuda" if cuda_available else "cpu",
            "name": (
                torch.cuda.get_device_name(0)
                if cuda_available
                else "cpu"
            ),
        },
        "selectionProtocol": {
            "selectedOn": "validation identities only",
            "testExcludedFromModelAndThresholdSelection": True,
            "testWasObservedByEarlierExperiments": True,
        },
        "calibrationPolicy": "validation_fixed_threshold",
        "cameraInvariantHead": camera_metadata,
        "selected": {
            "matrix": selected.matrix_name,
            "confidence": selected.confidence_name,
            "threshold": selected.threshold,
            "feasible": selected.feasible,
            "validationMetrics": asdict(selected.validation_metrics),
        },
        "fixedThresholdTestMetrics": asdict(fixed_test_metrics),
        "fixedThresholdTestWilson95": metric_wilson95(fixed_test_metrics),
        "testMetrics": asdict(fixed_test_metrics),
        "testWilson95": metric_wilson95(fixed_test_metrics),
        "testFeasible": test_feasible,
        "targetAutomaticDecisionAccuracy": 0.84,
        "targetMet": (
            selected.feasible
            and test_feasible
            and fixed_test_metrics.automatic_decision_accuracy >= 0.84
        ),
        "candidates": candidate_rows,
        "evidenceBoundary": {
            "dataset": args.dataset_label,
            "protocol": args.protocol_label,
            "officialBenchmarkProtocolUsed": False,
            "projectCctvGeneralizationProven": False,
            "automaticDecisionMetricIncludesDistractorRejection": True,
            "operatorReviewStillRequired": True,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "device": payload["device"],
                "selected": payload["selected"],
                "targetMet": payload["targetMet"],
                "testMetrics": payload["testMetrics"],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
