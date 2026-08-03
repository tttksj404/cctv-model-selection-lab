from __future__ import annotations

import numpy as np
import pytest

from scripts.prid2011_track_metrics import TrackEmbedding

torch = pytest.importorskip("torch")
metric_adapter = pytest.importorskip("scripts.train_prid2011_metric_adapter")
AdapterConfig = metric_adapter.AdapterConfig
ResidualMetricAdapter = metric_adapter.ResidualMetricAdapter
_train_arrays = metric_adapter._train_arrays
train_metric_adapter = metric_adapter.train_metric_adapter


def _track(identity: str, camera: str, vector: tuple[float, ...]) -> TrackEmbedding:
    values = np.asarray(vector, dtype=np.float32)
    values /= np.linalg.norm(values)
    return TrackEmbedding(
        track_id=f"{identity}-{camera}",
        identity=identity,
        role="gallery" if camera == "cam_a" else "query",
        camera=camera,
        split="train",
        vector=values,
        frame_count=5,
    )


def test_residual_adapter_starts_as_exact_normalized_identity() -> None:
    model = ResidualMetricAdapter(input_dim=4, rank=2, residual_scale=0.5)
    values = torch.tensor(
        [[1.0, 2.0, 3.0, 4.0], [4.0, 3.0, 2.0, 1.0]], dtype=torch.float32
    )

    actual = model(values)

    assert torch.allclose(actual, torch.nn.functional.normalize(values), atol=1e-7)


def test_train_arrays_rejects_single_camera_identity() -> None:
    tracks = [
        _track("a", "cam_a", (1.0, 0.0, 0.0, 0.0)),
        _track("a", "cam_b", (0.9, 0.1, 0.0, 0.0)),
        _track("b", "cam_a", (0.0, 1.0, 0.0, 0.0)),
    ]

    try:
        _train_arrays(tracks)
    except RuntimeError as exc:
        assert "at least two" in str(exc)
    else:
        raise AssertionError("single-camera identity was accepted")


def test_metric_adapter_trains_and_returns_normalized_vectors() -> None:
    tracks = [
        _track("a", "cam_a", (1.0, 0.0, 0.0, 0.0)),
        _track("a", "cam_b", (0.9, 0.1, 0.0, 0.0)),
        _track("b", "cam_a", (0.0, 1.0, 0.0, 0.0)),
        _track("b", "cam_b", (0.1, 0.9, 0.0, 0.0)),
    ]
    config = AdapterConfig(
        name="test",
        rank=2,
        residual_scale=0.25,
        epochs=2,
        learning_rate=0.001,
        arc_margin=0.2,
        triplet_margin=0.1,
        geometry_weight=0.1,
        preserve_weight=0.1,
        seed=7,
    )

    adapter, final_loss = train_metric_adapter(tracks, config, torch.device("cpu"))
    transformed = adapter.transform(np.stack([track.vector for track in tracks]))

    assert np.isfinite(final_loss)
    assert transformed.shape == (4, 4)
    assert np.allclose(np.linalg.norm(transformed, axis=1), 1.0, atol=1e-6)
