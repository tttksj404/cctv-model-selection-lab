from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding

FEATURE_NAMES = (
    "top_score",
    "forward_gap_1",
    "forward_gap_5",
    "forward_gap_20",
    "forward_tail_z",
    "forward_gap_ratio",
    "reverse_reciprocal_rank",
    "reverse_gap_1",
    "reverse_gap_5",
    "reverse_tail_z",
    "mutual_top1",
)


class OpenSetFeatureError(ValueError):
    pass


class OpenSetThresholdError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenSetBatch:
    features: np.ndarray
    known: np.ndarray
    top1_correct: np.ndarray
    correct_ranks: np.ndarray


@dataclass(frozen=True, slots=True)
class DecisionMetrics:
    query_tracks: int
    known_queries: int
    distractor_queries: int
    known_rank1: float
    known_recall_at5: float
    known_mrr: float
    distractor_false_match_rate: float
    false_reject_rate: float
    automatic_decision_accuracy: float


def _normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm <= 0.0:
        raise OpenSetFeatureError("track vector has zero norm")
    return np.asarray(vector / norm, dtype=np.float32)


def _tail_z(sorted_scores: np.ndarray, width: int) -> float:
    tail = sorted_scores[1 : min(len(sorted_scores), width + 1)]
    if len(tail) < 2:
        return 0.0
    spread = max(float(np.std(tail)), 1e-6)
    return float((sorted_scores[0] - np.mean(tail)) / spread)


def _gap(sorted_scores: np.ndarray, width: int) -> float:
    tail = sorted_scores[1 : min(len(sorted_scores), width + 1)]
    return float(sorted_scores[0] - np.mean(tail)) if len(tail) else 0.0


def extract_open_set_batch(tracks: Sequence[TrackEmbedding]) -> OpenSetBatch:
    queries = [track for track in tracks if track.role == "query"]
    gallery = [track for track in tracks if track.role == "gallery"]
    if len(queries) < 2 or len(gallery) < 2:
        raise OpenSetFeatureError(
            "open-set features require at least two query and gallery tracks"
        )
    query_matrix = np.stack([track.vector for track in queries])
    gallery_matrix = np.stack([track.vector for track in gallery])
    scores = query_matrix @ gallery_matrix.T
    gallery_identities = {track.identity for track in gallery}
    rows: list[list[float]] = []
    known_flags: list[bool] = []
    top1_flags: list[bool] = []
    correct_ranks: list[int] = []
    for query_index, query in enumerate(queries):
        forward_order = np.argsort(-scores[query_index])
        forward = scores[query_index, forward_order]
        top_gallery_index = int(forward_order[0])
        ranked_ids = [gallery[int(index)].identity for index in forward_order]
        known = query.identity in gallery_identities
        correct_rank = ranked_ids.index(query.identity) + 1 if known else 0
        reverse_order = np.argsort(-scores[:, top_gallery_index])
        reverse = scores[reverse_order, top_gallery_index]
        reverse_rank = int(np.flatnonzero(reverse_order == query_index)[0]) + 1
        forward_gap_5 = _gap(forward, 5)
        rows.append(
            [
                float(forward[0]),
                float(forward[0] - forward[1]),
                forward_gap_5,
                _gap(forward, 20),
                _tail_z(forward, 20),
                float((forward[0] - forward[1]) / max(forward_gap_5, 1e-6)),
                1.0 / reverse_rank,
                float(reverse[0] - reverse[1]),
                _gap(reverse, 5),
                _tail_z(reverse, 20),
                float(reverse_rank == 1),
            ]
        )
        known_flags.append(known)
        top1_flags.append(correct_rank == 1)
        correct_ranks.append(correct_rank)
    return OpenSetBatch(
        features=np.asarray(rows, dtype=np.float32),
        known=np.asarray(known_flags, dtype=np.bool_),
        top1_correct=np.asarray(top1_flags, dtype=np.bool_),
        correct_ranks=np.asarray(correct_ranks, dtype=np.int32),
    )


def _as_role(
    track: TrackEmbedding, role: str, episode: int
) -> TrackEmbedding:
    return TrackEmbedding(
        track_id=f"episode-{episode}-{role}-{track.track_id}",
        identity=track.identity,
        role=role,
        camera=track.camera,
        split="synthetic-train",
        vector=_normalize(track.vector),
        frame_count=track.frame_count,
    )


def build_training_episodes(
    tracks: Sequence[TrackEmbedding], episodes: int, seed: int
) -> OpenSetBatch:
    by_identity: dict[str, dict[str, TrackEmbedding]] = defaultdict(dict)
    for track in tracks:
        if track.split == "train":
            by_identity[track.identity][track.camera] = track
    paired = {
        identity: camera_tracks
        for identity, camera_tracks in by_identity.items()
        if len(camera_tracks) >= 2
    }
    if len(paired) < 40:
        raise OpenSetFeatureError(
            "at least 40 two-camera train identities are required"
        )
    identities = np.asarray(sorted(paired))
    rng = np.random.default_rng(seed)
    batches: list[OpenSetBatch] = []
    for episode in range(episodes):
        shuffled = rng.permutation(identities)
        gallery_count = int(rng.integers(48, min(72, len(shuffled) - 8) + 1))
        gallery_ids = shuffled[:gallery_count]
        unknown_ids = shuffled[gallery_count:]
        known_count = int(rng.integers(16, min(32, gallery_count) + 1))
        unknown_count = min(
            len(unknown_ids),
            int(rng.integers(8, min(24, len(unknown_ids)) + 1)),
        )
        known_ids = rng.choice(gallery_ids, size=known_count, replace=False)
        unknown_query_ids = rng.choice(
            unknown_ids, size=unknown_count, replace=False
        )
        first_camera, second_camera = (
            ("cam_a", "cam_b") if episode % 2 == 0 else ("cam_b", "cam_a")
        )
        episode_tracks = [
            _as_role(paired[str(identity)][first_camera], "gallery", episode)
            for identity in gallery_ids
        ]
        episode_tracks.extend(
            _as_role(paired[str(identity)][second_camera], "query", episode)
            for identity in np.concatenate([known_ids, unknown_query_ids])
        )
        batches.append(extract_open_set_batch(episode_tracks))
    return OpenSetBatch(
        features=np.concatenate([batch.features for batch in batches]),
        known=np.concatenate([batch.known for batch in batches]),
        top1_correct=np.concatenate([batch.top1_correct for batch in batches]),
        correct_ranks=np.concatenate([batch.correct_ranks for batch in batches]),
    )


def decision_metrics(
    batch: OpenSetBatch, accepted: np.ndarray
) -> DecisionMetrics:
    known = batch.known
    distractors = ~known
    known_ranks = batch.correct_ranks[known]
    reciprocal_ranks = np.divide(
        1.0,
        known_ranks,
        out=np.zeros_like(known_ranks, dtype=np.float64),
        where=known_ranks > 0,
    )
    auto_correct = (known & accepted & batch.top1_correct) | (
        distractors & ~accepted
    )
    return DecisionMetrics(
        query_tracks=len(batch.features),
        known_queries=int(np.sum(known)),
        distractor_queries=int(np.sum(distractors)),
        known_rank1=float(np.mean(batch.top1_correct[known])),
        known_recall_at5=float(np.mean((known_ranks > 0) & (known_ranks <= 5))),
        known_mrr=float(np.mean(reciprocal_ranks)),
        distractor_false_match_rate=float(np.mean(accepted[distractors])),
        false_reject_rate=float(np.mean(~accepted[known])),
        automatic_decision_accuracy=float(np.mean(auto_correct)),
    )


def _thresholds(probabilities: np.ndarray) -> list[float]:
    unique = np.unique(probabilities)
    if len(unique) > 256:
        unique = np.quantile(unique, np.linspace(0.0, 1.0, 256))
    midpoints = (unique[:-1] + unique[1:]) / 2.0
    return [-1e-6, *[float(value) for value in midpoints], 1.000001]


def select_threshold(
    batch: OpenSetBatch, probabilities: np.ndarray
) -> tuple[float, DecisionMetrics, bool]:
    best: tuple[tuple[float, ...], float, DecisionMetrics, bool] | None = None
    for threshold in _thresholds(probabilities):
        metrics = decision_metrics(batch, probabilities >= threshold)
        feasible = (
            metrics.distractor_false_match_rate <= 0.05
            and metrics.false_reject_rate <= 0.15
        )
        key = (
            float(feasible),
            metrics.automatic_decision_accuracy,
            -metrics.distractor_false_match_rate,
            -metrics.false_reject_rate,
            -threshold,
        )
        if best is None or key > best[0]:
            best = (key, threshold, metrics, feasible)
    if best is None:
        raise OpenSetThresholdError("threshold search produced no candidate")
    return best[1], best[2], best[3]
