from __future__ import annotations

import numpy as np
import pytest

from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_cache_ensemble import (
    CacheEnsembleError,
    _weight_candidates,
    fuse_track_caches,
)


def _track(
    track_id: str,
    vector: tuple[float, ...],
    *,
    identity: str = "person",
) -> TrackEmbedding:
    return TrackEmbedding(
        track_id=track_id,
        identity=identity,
        role="query",
        camera="cam_b",
        split="test",
        vector=np.asarray(vector, dtype=np.float32),
        frame_count=3,
    )


def test_fused_cosine_equals_weighted_model_cosines() -> None:
    caches = {
        "solider": [
            _track("a", (1.0, 0.0), identity="a"),
            _track("b", (0.0, 1.0), identity="b"),
        ],
        "clip": [
            _track("a", (1.0, 1.0), identity="a"),
            _track("b", (1.0, 0.0), identity="b"),
        ],
    }

    fused = fuse_track_caches(caches, {"solider": 0.75, "clip": 0.25})
    actual = float(fused[0].vector @ fused[1].vector)
    expected = 0.75 * 0.0 + 0.25 * (1.0 / np.sqrt(2.0))

    assert abs(actual - expected) < 1e-6


def test_fusion_rejects_cache_with_different_track_ids() -> None:
    caches = {
        "solider": [_track("a", (1.0, 0.0))],
        "clip": [_track("different", (1.0, 0.0))],
    }

    with pytest.raises(CacheEnsembleError, match="track ids differ"):
        fuse_track_caches(caches, {"solider": 0.5, "clip": 0.5})


def test_weight_candidates_support_arbitrary_secondary_backbones() -> None:
    rows = dict(_weight_candidates({"solider", "fastreid_agw", "dinov2"}))

    assert rows["solider0.90-dinov20.10"] == {
        "solider": 0.90,
        "dinov2": 0.10,
    }
    assert rows["solider0.50-dinov20.25-fastreid_agw0.25"] == {
        "solider": 0.50,
        "dinov2": 0.25,
        "fastreid_agw": 0.25,
    }
    assert all(abs(sum(weights.values()) - 1.0) < 1e-8 for weights in rows.values())

