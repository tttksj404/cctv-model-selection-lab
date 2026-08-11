from __future__ import annotations

from typing import Literal

from qwen_backend.orchestration_experiment import PairScoreRow, run_experiment


def _rows_for_query(
    split: Literal["validation", "test"], query_id: str, known: bool
) -> list[PairScoreRow]:
    query_identity = "person-a" if known else "unknown"
    scores = (
        ("gallery-a-" + split, "person-a", 0.95 if known else 0.10),
        ("gallery-b-" + split, "person-b", 0.20),
        ("gallery-c-" + split, "person-c", 0.15),
    )
    return [
        PairScoreRow(
            query_track_id=query_id,
            query_identity=query_identity,
            query_known=known,
            protocol="cross_camera_event_heldout",
            query_case_id="case-1",
            query_video_id="video-query-" + split,
            query_event_group_id="event-1",
            query_timestamp_ms=1000,
            query_camera="camera-query",
            gallery_track_id=gallery_id,
            gallery_identity=gallery_identity,
            gallery_case_id="case-1",
            gallery_video_id="video-gallery-" + split,
            gallery_event_group_id="event-1",
            gallery_timestamp_ms=2000,
            gallery_camera="camera-gallery",
            split=split,
            clip_score=clip,
            solider_score=clip,
            par_score=clip,
            qwen_score=clip,
        )
        for gallery_id, gallery_identity, clip in scores
    ]


def test_loop_calibrates_on_validation_and_evaluates_sealed_test() -> None:
    rows = tuple(
        _rows_for_query("validation", "query-val-known", True)
        + _rows_for_query("validation", "query-val-unknown", False)
        + _rows_for_query("test", "query-test-known", True)
        + _rows_for_query("test", "query-test-unknown", False)
    )

    result = run_experiment(
        rows,
        rounds=2,
        required_known_queries=1,
        required_distractor_queries=1,
    )

    assert result.status == "completed"
    assert result.selected_arm is not None
    assert result.selected_validation is not None
    assert result.selected_test is not None
    assert result.selected_test.known_rank1 == 1.0
    assert result.selected_test.known_recall_at5 == 1.0
    assert result.selected_test.distractor_false_match_rate == 0.0
    assert result.promotion_gate.passed is True
    assert len(result.data_fingerprint) == 64
    assert len(result.arm_results) == 6
    assert all("test" not in arm.model_dump() for arm in result.arm_results)


def test_gate_blocks_when_real_identity_evidence_is_too_small() -> None:
    rows = tuple(
        _rows_for_query("validation", "query-val-known", True)
        + _rows_for_query("validation", "query-val-unknown", False)
        + _rows_for_query("test", "query-test-known", True)
        + _rows_for_query("test", "query-test-unknown", False)
    )

    result = run_experiment(rows, rounds=1)

    assert result.status == "completed"
    assert result.promotion_gate.eligible is False
    assert result.promotion_gate.passed is False
    assert any(
        "insufficient held-out queries" in reason for reason in result.promotion_gate.reasons
    )


def test_cross_camera_protocol_rejects_same_camera_rows() -> None:
    row = _rows_for_query("validation", "query-val-known", True)[0].model_copy(
        update={"gallery_camera": "camera-query"}
    )

    try:
        run_experiment(
            (row, *_rows_for_query("test", "query-test-known", True)),
            rounds=1,
            required_known_queries=1,
            required_distractor_queries=1,
        )
    except ValueError as exc:
        assert "cameras to differ" in str(exc)
    else:
        raise AssertionError("same-camera row must not pass cross-camera protocol")


def test_pair_provenance_must_be_consistent_for_one_track() -> None:
    rows = _rows_for_query("validation", "query-val-known", True)
    rows[1] = rows[1].model_copy(update={"query_video_id": "different-video"})

    try:
        run_experiment(
            tuple(rows + _rows_for_query("test", "query-test-known", True)),
            rounds=1,
            required_known_queries=1,
            required_distractor_queries=1,
        )
    except ValueError as exc:
        assert "inconsistent provenance" in str(exc)
    else:
        raise AssertionError("inconsistent query provenance must be rejected")
