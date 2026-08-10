from __future__ import annotations

from pathlib import Path

import numpy as np

from scripts.prid2011_metric_head import (
    apply_metric_head,
    fit_kissme_head,
    with_alpha,
)
from scripts.prid2011_track_cache import load_track_cache, save_track_cache
from scripts.prid2011_track_metrics import (
    TrackEmbedding,
    calibrate_open_set,
    evaluate_retrieval,
    pool_tracks,
)


def _track(
    track_id: str,
    identity: str,
    role: str,
    vector: tuple[float, float, float],
) -> TrackEmbedding:
    return TrackEmbedding(
        track_id=track_id,
        identity=identity,
        role=role,
        camera="cam_a" if role == "query" else "cam_b",
        split="validation",
        vector=np.asarray(vector, dtype=np.float32),
        frame_count=3,
    )


def test_pool_tracks_normalizes_mean_embedding() -> None:
    rows: list[dict[str, object]] = [
        {
            "trackId": "query-1",
            "identityGroupId": "person-1",
            "benchmarkRole": "query",
            "split": "validation",
        },
        {
            "trackId": "query-1",
            "identityGroupId": "person-1",
            "benchmarkRole": "query",
            "split": "validation",
        },
        {
            "trackId": "gallery-1",
            "identityGroupId": "person-1",
            "benchmarkRole": "gallery",
            "split": "validation",
        },
    ]
    frame_embeddings = np.asarray(
        [[1.0, 0.0], [0.8, 0.2], [1.0, 0.0]],
        dtype=np.float32,
    )

    tracks = pool_tracks(rows, frame_embeddings)

    assert len(tracks) == 2
    assert tracks[0].frame_count == 2
    assert bool(np.isclose(np.linalg.norm(tracks[0].vector), 1.0))


def test_validation_calibration_is_applied_without_test_tuning() -> None:
    validation = [
        _track("vq1", "p1", "query", (1.0, 0.0, 0.0)),
        _track("vq2", "p2", "query", (0.0, 1.0, 0.0)),
        _track("vd1", "d1", "query", (0.0, 0.0, 1.0)),
        _track("vg1", "p1", "gallery", (0.99, 0.01, 0.0)),
        _track("vg2", "p2", "gallery", (0.01, 0.99, 0.0)),
    ]
    test = [
        _track("tq1", "p3", "query", (0.98, 0.02, 0.0)),
        _track("tq2", "p4", "query", (0.02, 0.98, 0.0)),
        _track("td1", "d2", "query", (0.0, 0.0, 1.0)),
        _track("tg1", "p3", "gallery", (1.0, 0.0, 0.0)),
        _track("tg2", "p4", "gallery", (0.0, 1.0, 0.0)),
    ]

    calibration = calibrate_open_set(validation)
    metrics = evaluate_retrieval(test, calibration)

    assert calibration.source == "validation"
    assert metrics.known_rank1 == 1.0
    assert metrics.distractor_false_match_rate == 0.0
    assert metrics.false_reject_rate == 0.0
    assert metrics.automatic_decision_accuracy == 1.0


def test_wrong_top1_is_not_counted_as_accepted_correct() -> None:
    tracks = [
        _track("q1", "p1", "query", (0.0, 1.0, 0.0)),
        _track("g1", "p1", "gallery", (1.0, 0.0, 0.0)),
        _track("g2", "p2", "gallery", (0.0, 1.0, 0.0)),
    ]

    metrics = evaluate_retrieval(tracks, None)

    assert metrics.known_rank1 == 0.0
    assert metrics.automatic_decision_accuracy == 0.0


def test_track_cache_round_trip(tmp_path: Path) -> None:
    cache_path = tmp_path / "tracks.npz"
    expected = [
        _track("q1", "p1", "query", (1.0, 0.0, 0.0)),
        _track("g1", "p1", "gallery", (0.9, 0.1, 0.0)),
    ]

    save_track_cache(cache_path, expected)
    actual = load_track_cache(cache_path)

    assert [track.track_id for track in actual] == ["q1", "g1"]
    assert np.allclose(actual[1].vector, expected[1].vector)


def test_kissme_head_is_fitted_only_from_cross_camera_train_pairs() -> None:
    tracks: list[TrackEmbedding] = []
    for identity_index in range(12):
        angle = identity_index * 0.25
        identity = f"train-{identity_index:02d}"
        tracks.extend(
            [
                TrackEmbedding(
                    f"a-{identity}",
                    identity,
                    "train",
                    "cam_a",
                    "train",
                    np.asarray([np.cos(angle), np.sin(angle), 0.2], dtype=np.float32),
                    4,
                ),
                TrackEmbedding(
                    f"b-{identity}",
                    identity,
                    "train",
                    "cam_b",
                    "train",
                    np.asarray(
                        [np.cos(angle), np.sin(angle), -0.2],
                        dtype=np.float32,
                    ),
                    4,
                ),
            ]
        )

    head = with_alpha(fit_kissme_head(tracks, 1e-2, 2), 0.5)
    adapted = apply_metric_head(tracks, head)

    assert head.dimension > 0
    assert len(adapted) == len(tracks)
    assert all(bool(np.isfinite(track.vector).all()) for track in adapted)
    assert all(bool(np.isclose(np.linalg.norm(track.vector), 1.0)) for track in adapted)

