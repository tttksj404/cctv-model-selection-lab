import pytest

from qwen_backend.cctv_identity_evaluation import (
    CCTVDataError,
    Decision,
    Split,
    TargetRole,
    TrackReference,
    TrackRetrievalPrediction,
    evaluate_identity_predictions,
    validate_track_split,
)


def reference(
    track_id: str,
    identity_group_id: str | None,
    target_role: TargetRole,
    split: Split = "test",
) -> TrackReference:
    return TrackReference(
        caseId="case-01",
        videoId="video-01",
        cameraId="camera-01",
        conditionGroupId="landscape-wide",
        trackId=track_id,
        split=split,
        targetRole=target_role,
        identityGroupId=identity_group_id,
        frameCount=30,
    )


def prediction(
    track_id: str, candidates: list[tuple[str, float]], decision: Decision
) -> TrackRetrievalPrediction:
    return TrackRetrievalPrediction(
        queryTrackId=track_id,
        candidates=[
            {"identityGroupId": identity_id, "score": score}
            for identity_id, score in candidates
        ],
        decision=decision,
    )


def test_track_heldout_metrics_are_computed_once_per_track() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("gallery-b", "person-b", "target", "gallery"),
        reference("track-a", "person-a", "target"),
        reference("track-b", "person-b", "distractor"),
        reference("track-u", None, "unknown"),
    )
    predictions = (
        prediction("track-a", [("person-a", 0.9), ("person-b", 0.2)], "match"),
        prediction("track-b", [("person-b", 0.8), ("person-a", 0.1)], "reject"),
        prediction("track-u", [("person-a", 0.7)], "match"),
    )

    report = evaluate_identity_predictions(references, predictions, model_name="test-model")

    assert report.status == "valid"
    assert report.known_query_count == 1
    assert report.predicted_track_count == 3
    assert report.rank1 == 1.0
    assert report.recall_at_5 == 1.0
    assert report.false_match_rate == 0.5
    assert report.false_reject_rate == 0.0
    assert report.review_rate == 0.0


def test_identity_cannot_leak_across_splits() -> None:
    references = (
        reference("track-a", "person-a", "target", "train"),
        reference("track-b", "person-a", "target", "test"),
    )

    try:
        validate_track_split(references)
    except CCTVDataError as error:
        assert "identityGroupId" in str(error)
    else:
        raise AssertionError("expected identity split leakage to fail closed")


def test_same_identity_can_span_test_only_conditions() -> None:
    references = (
        reference("track-a", "person-a", "target", "test_landscape"),
        reference("track-b", "person-a", "target", "test_portrait_fisheye"),
    )

    validate_track_split(references)


def test_missing_identity_labels_are_blocked() -> None:
    references = (
        reference("track-u", None, "target"),
        reference("track-d", "person-d", "distractor"),
        reference("track-x", None, "unknown"),
    )
    predictions = (prediction("track-u", [("person-a", 0.5)], "review"),)

    report = evaluate_identity_predictions(references, predictions, model_name="unlabeled")

    assert report.status == "blocked_missing_identity_labels"
    assert report.unlabeled_target_count == 1
    assert report.distractor_query_count == 1
    assert report.unknown_query_count == 1
    assert report.rank1 is None


def test_identity_score_is_blocked_without_explicit_gallery_track() -> None:
    references = (reference("track-a", "person-a", "target"),)
    predictions = (prediction("track-a", [("person-a", 0.99)], "match"),)

    report = evaluate_identity_predictions(references, predictions, model_name="no-gallery")

    assert report.status == "blocked_missing_gallery"
    assert report.gallery_track_count == 0
    assert report.gallery_identity_count == 0
    assert report.rank1 is None


def test_candidate_identity_must_exist_in_gallery() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("track-a", "person-a", "target"),
    )
    predictions = (prediction("track-a", [("person-b", 0.99)], "match"),)

    with pytest.raises(CCTVDataError, match="not present in gallery"):
        evaluate_identity_predictions(references, predictions, model_name="unknown-gallery")


def test_condition_specific_test_split_is_evaluated() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("track-a", "person-a", "target", "test_landscape"),
    )
    predictions = (prediction("track-a", [("person-a", 0.9)], "match"),)

    report = evaluate_identity_predictions(references, predictions, model_name="condition-test")

    assert report.status == "valid"
    assert report.rank1 == 1.0


def test_missing_prediction_stays_in_metric_denominators() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("gallery-b", "person-b", "target", "gallery"),
        reference("track-a", "person-a", "target"),
        reference("track-b", "person-b", "target"),
    )
    predictions = (prediction("track-a", [("person-a", 0.9)], "match"),)

    report = evaluate_identity_predictions(references, predictions, model_name="missing")

    assert report.status == "valid"
    assert report.known_query_count == 2
    assert report.rank1 == 0.5
    assert report.mean_average_precision == 0.5
    assert report.false_reject_rate == 0.5
    assert report.missing_prediction_count == 1
    assert report.query_without_gallery_count == 1


def test_false_match_rate_counts_missing_non_target_queries() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("gallery-b", "person-b", "target", "gallery"),
        reference("track-a", "person-a", "target"),
        reference("track-d", "person-b", "distractor"),
        reference("track-u", None, "unknown"),
    )
    predictions = (
        prediction("track-a", [("person-a", 0.9)], "match"),
        prediction("track-u", [("person-a", 0.8)], "match"),
    )

    report = evaluate_identity_predictions(references, predictions, model_name="non-target")

    assert report.false_match_rate == 0.5


def test_review_rate_uses_predicted_test_tracks() -> None:
    references = (
        reference("gallery-a", "person-a", "target", "gallery"),
        reference("gallery-b", "person-b", "target", "gallery"),
        reference("track-a", "person-a", "target"),
        reference("track-d", "person-b", "distractor"),
        reference("track-u", None, "unknown"),
    )
    predictions = (
        prediction("track-a", [("person-a", 0.9)], "match"),
        prediction("track-u", [("person-a", 0.8)], "review"),
    )

    report = evaluate_identity_predictions(references, predictions, model_name="review")

    assert report.review_rate == 0.5


def test_duplicate_candidate_identity_is_rejected() -> None:
    references = (reference("track-a", "person-a", "target"),)
    predictions = (
        prediction(
            "track-a",
            [("person-a", 0.9), ("person-a", 0.8)],
            "match",
        ),
    )

    with pytest.raises(CCTVDataError, match="duplicate candidate"):
        evaluate_identity_predictions(references, predictions, model_name="duplicate")

