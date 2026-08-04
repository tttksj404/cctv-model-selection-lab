from pathlib import Path

from qwen_backend.solider_clip_engine import EngineConfig, SoliderClipCandidateEngine
from qwen_backend.video_tracks import TrackFrame


def _engine() -> SoliderClipCandidateEngine:
    return SoliderClipCandidateEngine(
        EngineConfig(
            model_key="fixture-hybrid-v1",
            device="cpu",
            yolo_weights="fixture-yolo.pt",
            tracker="fixture-tracker.yaml",
            reid_checkpoint=None,
            solider_root=None,
            clip_checkpoint="fixture-clip",
            top_k=5,
            max_crops_per_track=1,
            detector_confidence=0.25,
            frame_stride=1,
            sample_every_seconds=1.0,
            crop_margin=0.0,
            reid_weight=1.0,
            clip_weight=0.0,
            aggregate_top_frames=1,
            reid_batch_size=1,
        )
    )


def _track(track_id: int, offset_ms: int) -> TrackFrame:
    return TrackFrame(
        track_id=track_id,
        frame_index=offset_ms,
        frame_offset_ms=offset_ms,
        frame_path=Path(f"frame-{track_id}.jpg"),
        crop_path=Path(f"crop-{track_id}.jpg"),
        left=10,
        top=20,
        right=40,
        bottom=80,
        detector_confidence=0.9,
    )


def test_track_aggregation_applies_an_optional_server_threshold() -> None:
    candidates = _engine()._aggregate_tracks(
        (_track(1, 1_000), _track(2, 2_000)),
        (0.79, 0.85),
        "SOLIDER",
        similarity_threshold=0.8,
    )

    assert [candidate.candidate_key for candidate in candidates] == ["track-2"]


def test_track_aggregation_preserves_ranking_when_server_omits_threshold() -> None:
    candidates = _engine()._aggregate_tracks(
        (_track(1, 1_000), _track(2, 2_000)),
        (0.79, 0.85),
        "SOLIDER",
        similarity_threshold=None,
    )

    assert [candidate.candidate_key for candidate in candidates] == ["track-2", "track-1"]
