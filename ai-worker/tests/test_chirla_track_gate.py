from __future__ import annotations

import numpy as np

from scripts.evaluate_chirla_track_gate import _rank, _track_rows


def _metadata() -> dict[str, object]:
    return {
        "query_path": [
            "root/track-a/frame-1.png",
            "root/track-a/frame-2.png",
            "root/track-b/frame-1.png",
            "root/track-b/frame-2.png",
        ],
        "query_identity": ["a", "a", "b", "b"],
        "query_camera": ["camera-1"] * 4,
        "query_sequence": ["sequence-1"] * 4,
    }


def test_track_gate_averages_frames_before_ranking() -> None:
    scores = np.asarray(
        [
            [0.40, 0.90],
            [0.90, 0.40],
            [0.85, 0.45],
            [0.45, 0.85],
        ],
        dtype=np.float32,
    )

    track_scores, targets, receipts = _track_rows(_metadata(), scores, ["a", "b"])

    assert track_scores.shape == (2, 2)
    assert np.allclose(track_scores, [[0.65, 0.65], [0.65, 0.65]])
    assert targets.tolist() == [0, 1]
    assert [receipt["frameCount"] for receipt in receipts] == [2, 2]


def test_rank_uses_stable_identity_order_for_ties() -> None:
    ranks = _rank(
        np.asarray([[0.5, 0.5], [0.6, 0.4]], dtype=np.float32),
        np.asarray([0, 1], dtype=np.int64),
    )

    assert ranks.tolist() == [1, 2]
