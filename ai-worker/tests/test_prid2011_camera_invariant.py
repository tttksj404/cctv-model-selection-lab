from __future__ import annotations

import numpy as np

from scripts.prid2011_track_metrics import TrackEmbedding
from scripts.tune_prid2011_camera_invariant import (
    TransformSpec,
    apply_camera_transform,
    fit_camera_transform,
)


def _track(
    identity: str,
    camera: str,
    vector: np.ndarray,
) -> TrackEmbedding:
    return TrackEmbedding(
        track_id=f"{identity}-{camera}",
        identity=identity,
        role="gallery" if camera == "cam_a" else "query",
        camera=camera,
        split="train",
        vector=np.asarray(vector / np.linalg.norm(vector), dtype=np.float32),
        frame_count=4,
    )


def test_camera_mean_correction_reduces_synthetic_camera_offset() -> None:
    tracks: list[TrackEmbedding] = []
    for index in range(20):
        identity = np.zeros(24, dtype=np.float32)
        identity[index % 20] = 1.0
        offset = np.zeros(24, dtype=np.float32)
        offset[-1] = 0.7
        tracks.append(_track(str(index), "cam_a", identity + offset))
        tracks.append(_track(str(index), "cam_b", identity - offset))
    before = np.mean(
        [
            float(tracks[index].vector @ tracks[index + 1].vector)
            for index in range(0, len(tracks), 2)
        ]
    )
    transform = fit_camera_transform(
        tracks,
        TransformSpec("mean", camera_mean_alpha=1.0, difference_rank=0, difference_alpha=0.0),
    )

    corrected = apply_camera_transform(tracks, transform)
    after = np.mean(
        [
            float(corrected[index].vector @ corrected[index + 1].vector)
            for index in range(0, len(corrected), 2)
        ]
    )

    assert after > before
    assert np.allclose(
        [np.linalg.norm(track.vector) for track in corrected],
        1.0,
        atol=1e-6,
    )

