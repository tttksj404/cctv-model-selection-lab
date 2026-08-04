import hashlib
import json
from pathlib import Path

from qwen_backend.cctv_review_queue import (
    ReviewQueueError,
    build_review_queue,
)
from qwen_backend.cctv_training_contract import CCTVTrainingSample
from scripts.build_cctv_review_queue import run


def _sample(sample_id: str, frame_path: str, augmentation: str) -> CCTVTrainingSample:
    return CCTVTrainingSample.model_validate(
        {
            "schemaVersion": "cctv-attribute-sample-v1",
            "sampleId": sample_id,
            "caseId": "case-01",
            "sourceFramePath": frame_path,
            "sourceFrameSha256": "a" * 64,
            "sourceVideoId": "video-01",
            "cameraId": "camera-01",
            "sequenceId": "sequence-01",
            "sourceTrackId": "track-01",
            "conditionGroupId": "landscape_room",
            "sourceSplit": "unassigned",
            "split": "unassigned",
            "cropPath": f"crops/{sample_id}.png",
            "cropSha256": "b" * 64,
            "augmentation": augmentation,
            "timestampMs": 1000,
            "identityGroupId": None,
            "targetRole": "unknown",
            "labelStatus": "needs_human_review",
            "labels": {
                "color": [],
                "clothing": [],
                "texture": [],
                "quality": [],
                "occlusion": [],
            },
            "sourceQuality": 0.8,
            "sourceQualityFlags": [],
            "sourceAttributes": {},
            "attributeEvidenceFrameIds": [],
            "trainingEligible": False,
            "approvalStatus": "unreviewed",
            "identityReviewStatus": "unreviewed",
            "teacherAgreement": False,
            "teacherSourceKind": "none",
            "teacherModel": None,
            "teacherTermsStatus": "not_applicable",
            "labelProvenance": "none",
            "reviewEvidencePath": None,
            "reviewEvidenceSha256": None,
            "teacherEvidencePath": None,
            "teacherEvidenceSha256": None,
        }
    )


def test_review_queue_has_one_item_per_original_frame() -> None:
    samples = (
        _sample("original", "frames/video/000001.jpg", "original"),
        _sample("brightness", "frames/video/000001.jpg", "brightness_low"),
        _sample("blur", "frames/video/000001.jpg", "blur"),
    )

    queue = build_review_queue(samples)

    assert len(queue) == 1
    assert queue[0].source_frame_path == "frames/video/000001.jpg"
    assert queue[0].augmentation_count == 3
    assert queue[0].training_eligible is False
    assert queue[0].identity_review_status == "unreviewed"


def test_review_queue_rejects_augmented_frame_without_original() -> None:
    samples = (_sample("brightness", "frames/video/000001.jpg", "brightness_low"),)

    try:
        build_review_queue(samples)
    except ReviewQueueError as error:
        assert "original" in str(error)
    else:
        raise AssertionError("expected missing original frame to be rejected")


def test_review_queue_rejects_duplicate_augmentation() -> None:
    samples = (
        _sample("original", "frames/video/000001.jpg", "original"),
        _sample("brightness-a", "frames/video/000001.jpg", "brightness_low"),
        _sample("brightness-b", "frames/video/000001.jpg", "brightness_low"),
    )

    try:
        build_review_queue(samples)
    except ReviewQueueError as error:
        assert "duplicate augmentation" in str(error)
    else:
        raise AssertionError("expected duplicate augmentation to be rejected")


def test_review_queue_output_path_can_be_checked_by_cli(tmp_path: Path) -> None:
    source = tmp_path / "frames/video/000001.jpg"
    crop = tmp_path / "crops/original.png"
    source.parent.mkdir(parents=True)
    crop.parent.mkdir(parents=True)
    source.write_bytes(b"source")
    crop.write_bytes(b"crop")
    sample = _sample("original", "frames/video/000001.jpg", "original").model_copy(
        update={
            "source_frame_sha256": hashlib.sha256(b"source").hexdigest(),
            "crop_sha256": hashlib.sha256(b"crop").hexdigest(),
        }
    )
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(sample.model_dump_json(by_alias=True) + "\n", encoding="utf-8")
    output = tmp_path / "queue/manifest.jsonl"

    summary = run(manifest, tmp_path, output)

    assert summary.queue_rows == 1
    assert output.is_file()
    assert output.with_suffix(".summary.json").is_file()
    row = json.loads(output.read_text(encoding="utf-8"))
    assert row["reviewId"].startswith("case-01/video-01/track-01")


def test_review_queue_rejects_asset_outside_workspace(tmp_path: Path) -> None:
    sample = _sample("original", "../outside.jpg", "original")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(sample.model_dump_json(by_alias=True) + "\n", encoding="utf-8")

    try:
        run(manifest, tmp_path, tmp_path / "queue.jsonl")
    except ReviewQueueError as error:
        assert "outside workspace" in str(error)
    else:
        raise AssertionError("expected an outside-workspace asset to be rejected")


def test_review_queue_rejects_asset_hash_mismatch(tmp_path: Path) -> None:
    source = tmp_path / "frames/video/000001.jpg"
    crop = tmp_path / "crops/original.png"
    source.parent.mkdir(parents=True)
    crop.parent.mkdir(parents=True)
    source.write_bytes(b"source")
    crop.write_bytes(b"crop")
    sample = _sample("original", "frames/video/000001.jpg", "original")
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(sample.model_dump_json(by_alias=True) + "\n", encoding="utf-8")

    try:
        run(manifest, tmp_path, tmp_path / "queue.jsonl")
    except ReviewQueueError as error:
        assert "hash does not match" in str(error)
    else:
        raise AssertionError("expected a hash mismatch to be rejected")


def test_review_queue_rejects_input_output_collision(tmp_path: Path) -> None:
    input_path = tmp_path / "manifest.jsonl"
    input_path.write_text("{}\n", encoding="utf-8")

    try:
        run(input_path, tmp_path, input_path)
    except ReviewQueueError as error:
        assert "must differ" in str(error)
    else:
        raise AssertionError("expected input and output collision to be rejected")


def test_review_ids_are_unique_for_distinct_source_frames() -> None:
    first = _sample("original-a", "frames/video/000001.jpg", "original")
    second = _sample("original-b", "frames/video/000002.jpg", "original")

    queue = build_review_queue((first, second))

    assert len({item.review_id for item in queue}) == 2
