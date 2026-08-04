from pathlib import Path

import pytest

from qwen_backend.cctv_sample_expansion import (
    DraftFrame,
    augmentation_names,
    crop_box_for_frame,
    make_sample,
)
from scripts.expand_cctv_attribute_samples import _safe_segment


def test_crop_box_for_frame_clamps_context_to_image() -> None:
    box = crop_box_for_frame(
        image_size=(100, 80),
        bbox=(5.0, 10.0, 60.0, 70.0),
        margin=0.2,
    )

    assert box == (0, 0, 71, 80)


def test_augmentation_names_are_deterministic_and_identity_safe() -> None:
    names = augmentation_names()

    assert names[0] == "original"
    assert names == (
        "original",
        "brightness_low",
        "brightness_high",
        "contrast_low",
        "contrast_high",
        "blur",
        "low_resolution",
    )


def test_make_sample_preserves_split_metadata(tmp_path: Path) -> None:
    row = DraftFrame.model_validate(
        {
            "schemaVersion": "cctv-track-v1.1",
            "caseId": "case-01",
            "videoId": "video-01",
            "cameraId": "camera-01",
            "conditionGroupId": "landscape_room",
            "sequenceId": "sequence-01",
            "trackId": "track-01",
            "split": "test",
            "targetRole": "unknown",
            "identityGroupId": None,
            "framePath": "frame.jpg",
            "timestampMs": 1234,
            "bbox": [10, 20, 40, 80],
        }
    )
    frame = tmp_path / "frame.jpg"
    crop = tmp_path / "crop.png"
    frame.write_bytes(b"frame")
    crop.write_bytes(b"crop")

    sample = make_sample(row, frame, crop, "original", tmp_path, 0)

    assert sample.case_id == "case-01"
    assert sample.camera_id == "camera-01"
    assert sample.sequence_id == "sequence-01"
    assert sample.timestamp_ms == 1234


def test_safe_segment_rejects_path_traversal() -> None:
    with pytest.raises(ValueError):
        _safe_segment("../outside")
