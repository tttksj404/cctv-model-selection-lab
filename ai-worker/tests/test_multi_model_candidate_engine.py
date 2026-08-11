from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qwen_backend.attribute_ensemble import (
    FrameAttributeScores,
    add_track_consistency,
    aggregate_track_scores,
    apply_identity_primary_score,
    color_scores,
    decide_track,
    fuse_track_scores,
    model_trace,
    parse_search_attributes,
)
from qwen_backend.multi_model_candidate_engine import select_evidence_frame
from qwen_backend.qwen_review_runtime import QwenReviewRuntime
from qwen_backend.realtime_models import SoliderCheckoutError
from qwen_backend.track_evidence import track_consistency
from qwen_backend.video_tracks import TrackFrame


def test_prompt_parser_keeps_upper_and_lower_colors_separate() -> None:
    attributes = parse_search_attributes("white shirt, black pants, eyeglasses, swept-back hair")

    assert attributes.upper_color == "white"
    assert attributes.lower_color == "black"
    assert attributes.glasses is True
    assert attributes.hair is True


def test_solider_checkout_error_is_a_runtime_dependency_failure() -> None:
    error = SoliderCheckoutError(Path("solider"), "working tree is not clean")

    assert isinstance(error, RuntimeError)


def test_roi_color_gate_rejects_navy_upper_for_white_upper() -> None:
    crop = np.zeros((200, 80, 3), dtype=np.uint8)
    crop[:125, :] = (70, 30, 15)  # navy in BGR
    crop[125:, :] = (0, 0, 0)
    attributes = parse_search_attributes("white shirt, black pants")

    upper, lower = color_scores(crop, attributes)

    assert upper is not None and upper < 0.20
    assert lower is not None and lower > 0.90


def test_ensemble_does_not_turn_missing_identity_into_a_positive_score() -> None:
    attributes = parse_search_attributes("white shirt, black pants")
    aggregate = aggregate_track_scores(
        (
            FrameAttributeScores(
                semantic=0.62,
                upper_color=0.95,
                lower_color=0.91,
                fine_attribute=None,
                identity=None,
                quality=0.9,
            ),
        ),
        attributes,
    )

    assert aggregate.identity is None
    assert 0.0 < aggregate.score < 0.9


def test_identity_primary_track_aggregation_uses_identity_quality_frames() -> None:
    attributes = parse_search_attributes("person")
    rows = (
        FrameAttributeScores(
            semantic=0.99,
            upper_color=None,
            lower_color=None,
            fine_attribute=None,
            identity=0.20,
            quality=0.9,
        ),
        FrameAttributeScores(
            semantic=0.40,
            upper_color=None,
            lower_color=None,
            fine_attribute=None,
            identity=0.90,
            quality=0.9,
        ),
    )

    semantic = aggregate_track_scores(rows, attributes, top_frames=1)
    identity = aggregate_track_scores(
        rows,
        attributes,
        top_frames=1,
        ranking_signal="identity",
    )

    assert semantic.identity == 0.20
    assert identity.identity == 0.90


def test_identity_primary_score_keeps_attribute_evidence_but_changes_ranking() -> None:
    attributes = parse_search_attributes("person")
    aggregate = aggregate_track_scores(
        (
            FrameAttributeScores(
                semantic=0.95,
                upper_color=None,
                lower_color=None,
                fine_attribute=0.80,
                identity=0.35,
                quality=0.9,
            ),
        ),
        attributes,
    )
    fused = fuse_track_scores(aggregate)
    primary = apply_identity_primary_score(fused, enabled=True)

    assert primary.score == 0.35
    assert primary.semantic == fused.semantic
    assert primary.fine_attribute == fused.fine_attribute


def test_required_color_mismatch_is_not_emitted_even_when_semantic_score_is_high() -> None:
    attributes = parse_search_attributes("white shirt, black pants")
    aggregate = aggregate_track_scores(
        (
            FrameAttributeScores(
                semantic=0.95,
                upper_color=0.08,
                lower_color=0.92,
                fine_attribute=0.80,
                identity=None,
                quality=0.95,
            ),
        ),
        attributes,
    )

    decision = decide_track(
        aggregate,
        attributes,
        minimum_output_score=0.30,
        color_reject_threshold=0.28,
        similarity_threshold=None,
    )

    assert decision.emit is False
    assert decision.reason == "required_color_mismatch"


def test_required_color_is_fail_closed_when_roi_score_is_unavailable() -> None:
    attributes = parse_search_attributes("white shirt")
    decision = decide_track(
        aggregate_track_scores(
            (
                FrameAttributeScores(
                    semantic=0.98,
                    upper_color=None,
                    lower_color=None,
                    fine_attribute=0.95,
                    identity=None,
                    quality=1.0,
                ),
            ),
            attributes,
        ),
        attributes,
        minimum_output_score=0.30,
        color_reject_threshold=0.35,
        similarity_threshold=None,
    )

    assert decision.emit is False
    assert decision.reason == "required_color_unavailable"


def test_model_trace_is_explicit_about_unavailable_teachers() -> None:
    trace = model_trace(
        (
            ("CLIP-ViT-L/14", "used"),
            ("SOLIDER", "not_configured:no_reference"),
            ("Qwen", "offline_server_verifier_not_configured"),
        )
    )

    assert "CLIP-ViT-L/14=used" in trace
    assert "SOLIDER=not_configured:no_reference" in trace
    assert "Qwen=offline_server_verifier_not_configured" in trace


def _frame(track_id: int, index: int, offset_ms: int, left: int = 10) -> TrackFrame:
    return TrackFrame(
        track_id=track_id,
        frame_index=index,
        frame_offset_ms=offset_ms,
        frame_path=Path(f"frame-{track_id}-{index}.jpg"),
        crop_path=Path(f"crop-{track_id}-{index}.jpg"),
        left=left,
        top=20,
        right=50 + left,
        bottom=100,
        detector_confidence=0.9,
    )


def test_temporal_and_spatial_signals_are_track_level_evidence() -> None:
    frames = (_frame(4, 0, 0), _frame(4, 1, 1_000, 12), _frame(4, 2, 2_000, 14))

    evidence = track_consistency(frames)

    assert 0.0 < evidence.temporal <= 1.0
    assert 0.0 < evidence.spatial <= 1.0


def test_missing_identity_and_gallery_are_not_silently_zeroed() -> None:
    attributes = parse_search_attributes("white shirt")
    rows = (
        FrameAttributeScores(
            semantic=0.70,
            upper_color=0.80,
            lower_color=None,
            fine_attribute=0.60,
            identity=None,
            quality=0.90,
            par_attribute=0.65,
        ),
        FrameAttributeScores(
            semantic=0.75,
            upper_color=0.85,
            lower_color=None,
            fine_attribute=0.65,
            identity=None,
            quality=0.90,
            par_attribute=0.70,
        ),
    )
    aggregate = aggregate_track_scores(rows, attributes)
    fused = fuse_track_scores(
        add_track_consistency(aggregate, frames=(_frame(1, 0, 0), _frame(1, 1, 1_000))),
    )

    assert fused.identity is None
    assert fused.historical is None
    assert fused.qwen is None
    assert 0.0 < fused.score < 1.0


def test_evidence_frame_prefers_a_visible_person_over_a_high_attribute_thumbnail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quality = {
        "crop-9-0.jpg": 0.30,
        "crop-small.jpg": 0.30,
        "crop-person.jpg": 0.92,
    }
    monkeypatch.setattr(
        "qwen_backend.multi_model_candidate_engine.crop_quality",
        lambda path: quality[str(path)],
    )
    frames = (
        _frame(9, 0, 0),
        TrackFrame(
            track_id=9,
            frame_index=1,
            frame_offset_ms=1_000,
            frame_path=Path("frame-person.jpg"),
            crop_path=Path("crop-person.jpg"),
            left=10,
            top=10,
            right=110,
            bottom=310,
            detector_confidence=0.85,
        ),
    )
    rows = (
        FrameAttributeScores(
            semantic=0.99,
            upper_color=0.99,
            lower_color=0.99,
            fine_attribute=None,
            identity=0.99,
            quality=0.30,
        ),
        FrameAttributeScores(
            semantic=0.70,
            upper_color=0.70,
            lower_color=0.70,
            fine_attribute=None,
            identity=0.70,
            quality=0.92,
        ),
    )

    selected = select_evidence_frame(frames, rows, minimum_quality=0.55)

    assert selected is not None
    assert selected.crop_path == Path("crop-person.jpg")


def test_evidence_frame_returns_none_when_no_person_crop_is_readable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "qwen_backend.multi_model_candidate_engine.crop_quality",
        lambda _path: 0.20,
    )

    assert select_evidence_frame((_frame(9, 0, 0),), (), minimum_quality=0.55) is None


def test_qwen_review_does_not_claim_usage_when_provider_is_not_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("QWEN_PROVIDER", "mock")

    runtime = QwenReviewRuntime(enabled=True, top_k=5)
    assert runtime.warm_up() == "unavailable:QWEN_PROVIDER_is_not_qwen"
    review, status = runtime.review(
        tmp_path / "candidate.jpg",
        case_id=1,
        camera_id=2,
        track_id=3,
        prompt="white shirt",
    )

    assert review is None
    assert status == "unavailable:QWEN_PROVIDER_is_not_qwen"
