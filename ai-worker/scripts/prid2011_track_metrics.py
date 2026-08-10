from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import pairwise

import numpy as np


@dataclass(frozen=True, slots=True)
class TrackEmbedding:
    track_id: str
    identity: str
    role: str
    camera: str
    split: str
    vector: np.ndarray
    frame_count: int


@dataclass(frozen=True, slots=True)
class Calibration:
    score_threshold: float
    margin_threshold: float
    source: str
    validation_accuracy: float


@dataclass(frozen=True, slots=True)
class RetrievalMetrics:
    query_tracks: int
    known_queries: int
    distractor_queries: int
    known_rank1: float
    known_recall_at5: float
    known_mrr: float
    distractor_false_match_rate: float
    false_reject_rate: float
    automatic_decision_accuracy: float


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    known: bool
    correct_rank: int | None
    top1_correct: bool
    score: float
    margin: float


def _text(row: Mapping[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be non-empty text")
    return value


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise ValueError("embedding vector has zero norm")
    return np.asarray(vector / norm, dtype=np.float32)


def pool_tracks(
    rows: Sequence[Mapping[str, object]], frame_embeddings: np.ndarray
) -> list[TrackEmbedding]:
    if len(rows) != len(frame_embeddings):
        raise ValueError("manifest rows and frame embeddings must have equal length")
    indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        indices[_text(row, "trackId")].append(index)

    tracks: list[TrackEmbedding] = []
    for track_id, frame_indices in indices.items():
        first = rows[frame_indices[0]]
        vectors = frame_embeddings[frame_indices]
        tracks.append(
            TrackEmbedding(
                track_id=track_id,
                identity=_text(first, "identityGroupId"),
                role=_text(first, "benchmarkRole"),
                camera=str(first.get("cameraId", "unknown")),
                split=_text(first, "split"),
                vector=_normalize(np.mean(vectors, axis=0)),
                frame_count=len(frame_indices),
            )
        )
    return tracks


def _outcomes(tracks: Sequence[TrackEmbedding]) -> list[QueryOutcome]:
    queries = [track for track in tracks if track.role == "query"]
    gallery = [track for track in tracks if track.role == "gallery"]
    if not queries or not gallery:
        raise ValueError("evaluation requires query and gallery tracks")
    gallery_matrix = np.stack([track.vector for track in gallery])
    gallery_identities = {track.identity for track in gallery}
    outcomes: list[QueryOutcome] = []
    for query in queries:
        scores = gallery_matrix @ query.vector
        order = [int(index) for index in np.argsort(-scores)]
        ranked_identities = [gallery[index].identity for index in order]
        known = query.identity in gallery_identities
        correct_rank = (
            ranked_identities.index(query.identity) + 1 if known else None
        )
        top_score = float(scores[order[0]])
        second_score = float(scores[order[1]]) if len(order) > 1 else -1.0
        outcomes.append(
            QueryOutcome(
                known=known,
                correct_rank=correct_rank,
                top1_correct=correct_rank == 1,
                score=top_score,
                margin=top_score - second_score,
            )
        )
    return outcomes


def _candidate_values(values: Sequence[float], lower_bound: float) -> list[float]:
    unique = sorted(set(values))
    if len(unique) > 64:
        quantiles = np.linspace(0.0, 1.0, 64)
        unique = sorted(
            set(
                float(value)
                for value in np.quantile(np.asarray(unique), quantiles)
            )
        )
    midpoints = [(left + right) / 2.0 for left, right in pairwise(unique)]
    return [lower_bound, *midpoints, unique[-1] + 1e-6]


def calibrate_open_set(tracks: Sequence[TrackEmbedding]) -> Calibration:
    outcomes = _outcomes(tracks)
    if not any(not outcome.known for outcome in outcomes):
        return Calibration(-1.0, -2.0, "validation", 0.0)
    score_values = _candidate_values([item.score for item in outcomes], -1.0)
    margin_values = _candidate_values([item.margin for item in outcomes], -2.0)
    best_key = (-1.0, -1.0, -1.0, -1.0, -2.0)
    best_thresholds = (-1.0, -2.0)
    for score_threshold in score_values:
        for margin_threshold in margin_values:
            known_count = sum(item.known for item in outcomes)
            distractor_count = len(outcomes) - known_count
            accepted = [
                item.score >= score_threshold and item.margin >= margin_threshold
                for item in outcomes
            ]
            correct = sum(
                (item.known and decision and item.top1_correct)
                or (not item.known and not decision)
                for item, decision in zip(outcomes, accepted, strict=True)
            )
            false_matches = sum(
                not item.known and decision
                for item, decision in zip(outcomes, accepted, strict=True)
            )
            false_rejects = sum(
                item.known and not decision
                for item, decision in zip(outcomes, accepted, strict=True)
            )
            candidate_key = (
                correct / len(outcomes),
                -(false_matches / max(1, distractor_count)),
                -(false_rejects / max(1, known_count)),
                -score_threshold,
                -margin_threshold,
            )
            if candidate_key > best_key:
                best_key = candidate_key
                best_thresholds = (score_threshold, margin_threshold)
    return Calibration(*best_thresholds, "validation", best_key[0])


def evaluate_retrieval(
    tracks: Sequence[TrackEmbedding],
    calibration: Calibration | None,
) -> RetrievalMetrics:
    outcomes = _outcomes(tracks)
    known = [item for item in outcomes if item.known]
    distractors = [item for item in outcomes if not item.known]
    thresholds = calibration or Calibration(-1.0, -2.0, "none", 0.0)
    accepted = [
        item.score >= thresholds.score_threshold
        and item.margin >= thresholds.margin_threshold
        for item in outcomes
    ]
    auto_correct = sum(
        (item.known and decision and item.top1_correct)
        or (not item.known and not decision)
        for item, decision in zip(outcomes, accepted, strict=True)
    )
    false_matches = sum(
        not item.known and decision
        for item, decision in zip(outcomes, accepted, strict=True)
    )
    false_rejects = sum(
        item.known and not decision
        for item, decision in zip(outcomes, accepted, strict=True)
    )
    return RetrievalMetrics(
        query_tracks=len(outcomes),
        known_queries=len(known),
        distractor_queries=len(distractors),
        known_rank1=sum(item.top1_correct for item in known) / max(1, len(known)),
        known_recall_at5=sum(
            item.correct_rank is not None and item.correct_rank <= 5 for item in known
        )
        / max(1, len(known)),
        known_mrr=sum(1.0 / item.correct_rank for item in known if item.correct_rank)
        / max(1, len(known)),
        distractor_false_match_rate=false_matches / max(1, len(distractors)),
        false_reject_rate=false_rejects / max(1, len(known)),
        automatic_decision_accuracy=auto_correct / len(outcomes),
    )

