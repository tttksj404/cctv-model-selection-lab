from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")
import numpy as np  # noqa: E402

from scripts.finetune_prid2011_solider_backbone import (  # noqa: E402
    ArcMarginHead,
    _continuous_validation_metrics,
    _validation_key,
    batch_hard_triplet,
    part_triplet,
)
from scripts.prid2011_track_metrics import TrackEmbedding  # noqa: E402


def test_reid_losses_are_finite_and_backpropagate() -> None:
    features = torch.randn(8, 16, requires_grad=True)
    labels = torch.tensor([0, 0, 1, 1, 2, 2, 3, 3])
    feature_map = torch.randn(8, 16, 8, 4, requires_grad=True)
    head = ArcMarginHead(16, 4, scale=32.0, margin=0.3)

    arc = torch.nn.functional.cross_entropy(head(features, labels), labels)
    global_triplet = batch_hard_triplet(features, labels, margin=0.2)
    local_triplet = part_triplet(feature_map, labels, parts=4, margin=0.2)
    loss = arc + global_triplet + local_triplet
    loss.backward()

    assert torch.isfinite(loss)
    assert features.grad is not None
    assert feature_map.grad is not None
    assert head.weight.grad is not None


def test_continuous_validation_metrics_reward_open_set_separation() -> None:
    def track(
        name: str,
        identity: str,
        role: str,
        vector: list[float],
    ) -> TrackEmbedding:
        array = np.asarray(vector, dtype=np.float32)
        array /= np.linalg.norm(array)
        return TrackEmbedding(
            track_id=name,
            identity=identity,
            role=role,
            camera="cam",
            split="validation",
            vector=array,
            frame_count=1,
        )

    separated = [
        track("g1", "a", "gallery", [1.0, 0.0]),
        track("g2", "b", "gallery", [0.0, 1.0]),
        track("q1", "a", "query", [1.0, 0.0]),
        track("qd", "unknown", "query", [-1.0, -1.0]),
    ]
    weak = [
        track("g1", "a", "gallery", [1.0, 0.0]),
        track("g2", "b", "gallery", [0.0, 1.0]),
        track("q1", "a", "query", [0.8, 0.6]),
        track("qd", "unknown", "query", [0.7, 0.7]),
    ]
    strong_metrics = _continuous_validation_metrics(separated)
    weak_metrics = _continuous_validation_metrics(weak)
    assert (
        strong_metrics["known_distractor_score_gap"]
        > weak_metrics["known_distractor_score_gap"]
    )
    base = {
        "automatic_decision_accuracy": 1.0,
        "known_rank1": 1.0,
        "known_recall_at5": 1.0,
        "distractor_false_match_rate": 0.0,
        "false_reject_rate": 0.0,
    }
    assert _validation_key({**base, **strong_metrics}) > _validation_key(
        {**base, **weak_metrics}
    )

