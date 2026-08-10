from __future__ import annotations

import json
from pathlib import Path

from scripts.build_cctv_identity_result import build_result


def _write(path: Path, value: str) -> Path:
    path.write_text(value, encoding="utf-8")
    return path


def test_result_is_blocked_until_identity_labels_are_reviewed(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.jsonl",
        json.dumps(
            {
                "caseId": "case-01",
                "videoId": "video-01",
                "cameraId": "camera-01",
                "conditionGroupId": "landscape-wide",
                "trackId": "track-a",
                "split": "test_landscape",
                "targetRole": "unknown",
                "identityGroupId": None,
                "framePath": "frame.jpg",
            }
        )
        + "\n",
    )
    predictions = _write(
        tmp_path / "predictions.jsonl",
        json.dumps(
            {
                "queryTrackId": "track-a",
                "candidates": [{"identityGroupId": "person-a", "score": 0.5}],
                "decision": "review",
            }
        )
        + "\n",
    )
    attributes = _write(
        tmp_path / "attributes.json",
        json.dumps(
            {"metrics": {"test": {"track_exact_match": 0.9, "mA": 0.9, "InsF1": 0.9}}}
        ),
    )

    result = build_result(manifest, predictions, attributes, "test-model")

    assert result["measurementStatus"] == "blocked_missing_reviewed_identity_labels"
    eligibility = result["evaluationEligibility"]
    assert eligibility["identityLabelsAvailable"] is False
    assert eligibility["trackHeldoutMetricsEligible"] is False


def test_result_preserves_missing_gallery_status(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.jsonl",
        json.dumps(
            {
                "caseId": "case-01",
                "videoId": "video-01",
                "cameraId": "camera-01",
                "conditionGroupId": "landscape-wide",
                "trackId": "track-a",
                "split": "test_landscape",
                "targetRole": "target",
                "identityGroupId": "person-a",
                "framePath": "frame.jpg",
            }
        )
        + "\n",
    )
    predictions = _write(
        tmp_path / "predictions.jsonl",
        json.dumps(
            {
                "queryTrackId": "track-a",
                "candidates": [{"identityGroupId": "person-a", "score": 0.5}],
                "decision": "review",
            }
        )
        + "\n",
    )
    attributes = _write(
        tmp_path / "attributes.json",
        json.dumps({"metrics": {"test": {}}}),
    )

    result = build_result(manifest, predictions, attributes, "missing-gallery")

    assert result["measurementStatus"] == "blocked_missing_gallery"
    eligibility = result["evaluationEligibility"]
    assert eligibility["identityLabelsAvailable"] is True
    assert eligibility["trackHeldoutMetricsEligible"] is False


def test_result_marks_single_identity_as_local_pilot(tmp_path: Path) -> None:
    manifest = _write(
        tmp_path / "manifest.jsonl",
        "\n".join(
            json.dumps(
                {
                    "caseId": "case-01",
                    "videoId": "video-01",
                    "cameraId": "camera-01",
                    "conditionGroupId": "landscape-wide",
                    "trackId": track_id,
                    "split": split,
                    "targetRole": "target",
                    "identityGroupId": "person-a",
                    "framePath": "frame.jpg",
                }
            )
            for track_id, split in (("gallery-a", "gallery"), ("track-a", "test_landscape"))
        )
        + "\n",
    )
    predictions = _write(
        tmp_path / "predictions.jsonl",
        json.dumps(
            {
                "queryTrackId": "track-a",
                "candidates": [{"identityGroupId": "person-a", "score": 0.9}],
                "decision": "match",
            }
        )
        + "\n",
    )
    attributes = _write(
        tmp_path / "attributes.json",
        json.dumps({"metrics": {"test": {"track_exact_match": 0.9, "mA": 0.9, "InsF1": 0.9}}}),
    )

    result = build_result(manifest, predictions, attributes, "pilot")

    assert result["measurementScope"] == "local_identity_pilot"
    assert result["promotionEligible"] is False

