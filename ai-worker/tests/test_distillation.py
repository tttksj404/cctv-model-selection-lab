import hashlib
import json
from pathlib import Path

import pytest

from qwen_backend.distillation import (
    DistillationDataError,
    DistillationSample,
    file_sha256,
    to_qwen_record,
)


def make_sample(image_path: str, source_hash: str) -> DistillationSample:
    return DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": "sample-001",
            "imagePath": image_path,
            "attributes": {
                "color": "red",
                "clothing": "jacket",
                "objectName": "person",
            },
            "decision": "match",
            "confidence": 0.91,
            "provenance": {
                "sourceKind": "open_model",
                "teacherModel": "grounding-dino-sam2-local",
                "promptVersion": "candidate-v1",
                "sourceHash": source_hash,
                "approvalStatus": "approved",
                "reviewedBy": "qa-fixture",
            },
            "geometry": {"bbox": {"bbox2d": [1, 2, 50, 90]}, "trackId": 3},
        }
    )


def test_distillation_sample_converts_to_official_qwen_shape(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"test-image")
    digest = file_sha256(image)
    record = to_qwen_record(make_sample("candidate.jpg", digest), tmp_path)

    dumped = record.model_dump(mode="json", by_alias=True)
    assert dumped["image"] == "candidate.jpg"
    assert dumped["conversations"][0]["from"] == "human"
    assert "<image>" in dumped["conversations"][0]["value"]
    assert json.loads(dumped["conversations"][1]["value"])["decision"] == "match"


def test_hash_mismatch_blocks_training_record(tmp_path: Path) -> None:
    image = tmp_path / "candidate.png"
    image.write_bytes(b"test-image")
    wrong_hash = hashlib.sha256(b"different-image").hexdigest()

    with pytest.raises(DistillationDataError, match="source hash mismatch"):
        to_qwen_record(make_sample("candidate.png", wrong_hash), tmp_path)


def test_invalid_geometry_is_rejected() -> None:
    with pytest.raises(ValueError, match="bbox2d"):
        DistillationSample.model_validate(
            {
                "schemaVersion": "distillation-v1",
                "sampleId": "sample-001",
                "imagePath": "candidate.jpg",
                "attributes": {},
                "decision": "match",
                "confidence": 0.5,
                "provenance": {
                    "sourceKind": "open_model",
                    "teacherModel": "local",
                    "promptVersion": "v1",
                    "sourceHash": "0" * 64,
                    "approvalStatus": "approved",
                    "reviewedBy": "qa-fixture",
                },
                "geometry": {"bbox": {"bbox2d": [50, 90, 1, 2]}},
            }
        )


def test_unapproved_teacher_record_cannot_become_training_record(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"test-image")
    sample = DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": "sample-pending",
            "imagePath": "candidate.jpg",
            "attributes": {"color": "red"},
            "decision": "review",
            "confidence": 0.5,
            "provenance": {
                "sourceKind": "open_model",
                "teacherModel": "grounding-dino-sam2-local",
                "promptVersion": "candidate-v1",
                "sourceHash": file_sha256(image),
            },
        }
    )

    with pytest.raises(DistillationDataError, match="not approved"):
        to_qwen_record(sample, tmp_path)

