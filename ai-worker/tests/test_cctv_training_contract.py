import hashlib
from pathlib import Path

import pytest

from qwen_backend.cctv_training_contract import (
    CCTVTrainingSample,
    TrainingManifestError,
    load_training_manifest,
    validate_training_manifest,
)


def _sample(
    sample_id: str, split: str, identity: str, condition: str, workspace: Path
) -> CCTVTrainingSample:
    frame = workspace / f"frame-{sample_id}.jpg"
    crop = workspace / f"crop-{sample_id}.png"
    review = workspace / f"review-{sample_id}.json"
    frame.write_bytes(b"frame")
    crop.write_bytes(b"crop")
    review.write_bytes(b"review")
    return CCTVTrainingSample.model_validate(
        {
            "schemaVersion": "cctv-attribute-sample-v1",
            "sampleId": sample_id,
            "caseId": "case-01",
            "sourceFramePath": frame.name,
            "sourceFrameSha256": hashlib.sha256(frame.read_bytes()).hexdigest(),
            "sourceVideoId": f"video-{condition}",
            "cameraId": "camera-01",
            "sequenceId": f"sequence-{condition}",
            "sourceTrackId": f"track-{sample_id}",
            "conditionGroupId": condition,
            "sourceSplit": "reviewed",
            "split": split,
            "cropPath": crop.name,
            "cropSha256": hashlib.sha256(crop.read_bytes()).hexdigest(),
            "augmentation": "original",
            "timestampMs": 100,
            "identityGroupId": identity,
            "targetRole": "target",
            "labelStatus": "human_reviewed",
            "labels": {
                "color": ["navy"],
                "clothing": ["jacket"],
                "texture": ["solid"],
                "quality": ["0.9"],
                "occlusion": ["0.1"],
            },
            "trainingEligible": True,
            "approvalStatus": "approved",
            "identityReviewStatus": "human_reviewed",
            "teacherAgreement": False,
            "teacherSourceKind": "none",
            "teacherModel": None,
            "teacherTermsStatus": "not_applicable",
            "labelProvenance": "human_review",
            "reviewEvidencePath": review.name,
            "reviewEvidenceSha256": hashlib.sha256(review.read_bytes()).hexdigest(),
            "teacherEvidencePath": None,
            "teacherEvidenceSha256": None,
        }
    )


def test_training_manifest_accepts_grouped_condition_holdouts(tmp_path: Path) -> None:
    report = validate_training_manifest(
        (
            _sample("train-01", "train", "person-train", "external", tmp_path),
            _sample(
                "landscape-01", "test_landscape", "person-landscape", "landscape_room", tmp_path
            ),
            _sample(
                "portrait-01",
                "test_portrait_fisheye",
                "person-portrait",
                "portrait_fisheye",
                tmp_path,
            ),
        ),
        workspace=tmp_path,
    )

    assert report.status == "valid"
    assert report.error_count == 0
    assert report.identity_groups == 3


def test_training_manifest_accepts_same_identity_across_test_conditions(tmp_path: Path) -> None:
    report = validate_training_manifest(
        (
            _sample("landscape-01", "test_landscape", "person-same", "landscape_room", tmp_path),
            _sample(
                "portrait-01",
                "test_portrait_fisheye",
                "person-same",
                "portrait_fisheye",
                tmp_path,
            ),
        ),
        workspace=tmp_path,
    )

    assert report.status == "valid"
    assert report.error_count == 0
    assert report.identity_groups == 1


def test_training_manifest_blocks_identity_split_leak(tmp_path: Path) -> None:
    report = validate_training_manifest(
        (
            _sample("train-01", "train", "person-same", "external", tmp_path),
            _sample("test-01", "test_landscape", "person-same", "landscape_room", tmp_path),
        ),
        workspace=tmp_path,
    )

    assert report.status == "blocked"
    assert any("identityGroupId crosses split" in error for error in report.errors)


def test_training_manifest_blocks_temporal_leak(tmp_path: Path) -> None:
    first = _sample("train-01", "train", "person-train", "external", tmp_path)
    second = _sample("test-01", "test_landscape", "person-test", "landscape_room", tmp_path)
    second = second.model_copy(
        update={
            "source_video_id": first.source_video_id,
            "sequence_id": first.sequence_id,
            "timestamp_ms": 1000,
        }
    )

    report = validate_training_manifest((first, second), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("temporal embargo violated" in error for error in report.errors)


def test_training_manifest_blocks_teacher_without_provenance(tmp_path: Path) -> None:
    sample = _sample(
        "teacher-01", "test_portrait_fisheye", "person-teacher", "portrait_fisheye", tmp_path
    )
    sample = sample.model_copy(
        update={
            "label_status": "teacher_agreed",
            "teacher_agreement": True,
            "teacher_source_kind": "sonnet",
            "teacher_model": "claude-sonnet-5",
            "teacher_terms_status": "pending",
            "label_provenance": "teacher_agreement",
        }
    )

    report = validate_training_manifest((sample,), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("teacher terms are not approved" in error for error in report.errors)


def test_training_manifest_blocks_normalized_identity_split_leak(tmp_path: Path) -> None:
    report = validate_training_manifest(
        (
            _sample("train-01", "train", "person-same", "external", tmp_path),
            _sample("test-01", "test_landscape", " PERSON-SAME ", "landscape_room", tmp_path),
        ),
        workspace=tmp_path,
    )

    assert report.status == "blocked"
    assert any("identityGroupId crosses split" in error for error in report.errors)


def test_training_manifest_blocks_protected_condition_override(tmp_path: Path) -> None:
    report = validate_training_manifest(
        (
            _sample("train-01", "train", "person-train", "external", tmp_path),
            _sample(
                "landscape-01", "test_landscape", "person-landscape", "landscape_room", tmp_path
            ),
            _sample(
                "portrait-01",
                "test_portrait_fisheye",
                "person-portrait",
                "portrait_fisheye", tmp_path
            ),
        ),
        condition_holdouts={"landscape_room": "train"},
        workspace=tmp_path,
    )

    assert report.status == "blocked"
    assert any("protected holdout cannot be changed" in error for error in report.errors)


def test_training_manifest_blocks_augmentation_in_test_split(tmp_path: Path) -> None:
    sample = _sample("test-01", "test_landscape", "person-test", "landscape_room", tmp_path)
    sample = sample.model_copy(update={"augmentation": "brightness_low"})

    report = validate_training_manifest((sample,), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("non-train split must use original augmentation" in error for error in report.errors)


def test_training_manifest_blocks_invalid_quality_value(tmp_path: Path) -> None:
    sample = _sample("test-01", "test_landscape", "person-test", "landscape_room", tmp_path)
    sample = sample.model_copy(
        update={"labels": {**sample.labels, "quality": ("not-a-number",)}}
    )

    report = validate_training_manifest((sample,), workspace=tmp_path)

    assert report.status == "blocked"
    assert any("quality must be a float" in error for error in report.errors)


def test_load_training_manifest_rejects_duplicate_json_keys(tmp_path) -> None:
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text('{"sampleId":"first","sampleId":"second"}\n', encoding="utf-8")

    with pytest.raises(TrainingManifestError):
        load_training_manifest(manifest)
