from __future__ import annotations

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_open_set_head import (
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)


def track(
    track_id: str,
    identity: str,
    role: str,
    vector: tuple[float, ...],
) -> TrackEmbedding:
    array = np.asarray(vector, dtype=np.float32)
    array /= np.linalg.norm(array)
    return TrackEmbedding(
        track_id=track_id,
        identity=identity,
        role=role,
        camera="camera",
        split="validation",
        vector=array,
        frame_count=4,
    )


def test_extract_open_set_batch_includes_identity_and_distractor_queries() -> None:
    tracks = [
        track("g-a", "a", "gallery", (1.0, 0.0, 0.0)),
        track("g-b", "b", "gallery", (0.0, 1.0, 0.0)),
        track("q-a", "a", "query", (0.99, 0.01, 0.0)),
        track("q-x", "x", "query", (0.7, 0.7, 0.1)),
    ]

    batch = extract_open_set_batch(tracks)

    assert batch.features.shape == (2, 11)
    assert batch.known.tolist() == [True, False]
    assert batch.top1_correct.tolist() == [True, False]
    assert batch.correct_ranks.tolist() == [1, 0]


def test_threshold_selection_enforces_false_match_and_false_reject_limits() -> None:
    batch = extract_open_set_batch(
        [
            track("g-a", "a", "gallery", (1.0, 0.0, 0.0)),
            track("g-b", "b", "gallery", (0.0, 1.0, 0.0)),
            track("q-a1", "a", "query", (0.99, 0.01, 0.0)),
            track("q-a2", "a", "query", (0.98, 0.02, 0.0)),
            track("q-a3", "a", "query", (0.97, 0.03, 0.0)),
            track("q-a4", "a", "query", (0.96, 0.04, 0.0)),
            track("q-x1", "x1", "query", (0.7, 0.7, 0.1)),
            track("q-x2", "x2", "query", (0.7, 0.7, -0.1)),
            track("q-x3", "x3", "query", (0.6, 0.6, 0.5)),
            track("q-x4", "x4", "query", (0.6, 0.6, -0.5)),
        ]
    )
    probabilities = np.asarray(
        [0.95, 0.9, 0.85, 0.8, 0.2, 0.15, 0.1, 0.05], dtype=np.float32
    )

    threshold, metrics, feasible = select_threshold(batch, probabilities)
    decisions = probabilities >= threshold
    independently_scored = decision_metrics(batch, decisions)

    assert feasible is True
    assert metrics == independently_scored
    assert metrics.automatic_decision_accuracy == 1.0
    assert metrics.distractor_false_match_rate == 0.0
    assert metrics.false_reject_rate == 0.0

