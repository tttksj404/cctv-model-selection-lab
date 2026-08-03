from __future__ import annotations

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_cross_episode_head import fit_cross_episode_head


def _tracks() -> list[TrackEmbedding]:
    rng = np.random.default_rng(20260729)
    rows: list[TrackEmbedding] = []
    for index in range(80):
        identity = f"p{index:03d}"
        base = rng.normal(size=32)
        base /= np.linalg.norm(base)
        for camera, noise in (("cam_a", 0.02), ("cam_b", 0.04)):
            vector = base + rng.normal(scale=noise, size=base.shape)
            vector /= np.linalg.norm(vector)
            rows.append(
                TrackEmbedding(
                    track_id=f"{identity}-{camera}",
                    identity=identity,
                    role="gallery" if camera == "cam_a" else "query",
                    camera=camera,
                    split="train",
                    vector=vector.astype(np.float32),
                    frame_count=4,
                )
            )
    for index in range(16):
        identity = f"v{index:03d}"
        base = rng.normal(size=32)
        base /= np.linalg.norm(base)
        for camera, role in (("cam_a", "gallery"), ("cam_b", "query")):
            vector = base + rng.normal(scale=0.03, size=base.shape)
            vector /= np.linalg.norm(vector)
            rows.append(
                TrackEmbedding(
                    track_id=f"{identity}-{camera}",
                    identity=identity,
                    role=role,
                    camera=camera,
                    split="validation",
                    vector=vector.astype(np.float32),
                    frame_count=4,
                )
            )
    for index in range(8):
        identity = f"u{index:03d}"
        vector = rng.normal(size=32)
        vector /= np.linalg.norm(vector)
        rows.append(
            TrackEmbedding(
                track_id=f"{identity}-cam_b",
                identity=identity,
                role="query",
                camera="cam_b",
                split="validation",
                vector=vector.astype(np.float32),
                frame_count=4,
            )
        )
    return rows


def test_cross_episode_head_uses_independent_calibration_stream() -> None:
    name, _, threshold, selected, candidates = fit_cross_episode_head(
        _tracks(),
        episodes=8,
        seed=7,
    )

    assert name == selected["name"]
    assert np.isfinite(threshold)
    assert len(candidates) == 4
    assert selected["calibration_metrics"]["query_tracks"] > 0
    assert selected["validation_metrics"]["query_tracks"] == 24
