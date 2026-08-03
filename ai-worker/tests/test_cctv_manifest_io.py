from __future__ import annotations

import json
from pathlib import Path

import pytest

from qwen_backend.cctv_identity_evaluation import CCTVDataError
from qwen_backend.cctv_manifest_io import (
    identity_label_sha256,
    load_track_predictions,
    load_track_references,
    manifest_sha256,
)


def _frame(track_id: str = "track-a", identity: str | None = "person-a") -> dict[str, object]:
    return {
        "caseId": "case-01",
        "videoId": "video-01",
        "cameraId": "camera-01",
        "conditionGroupId": "landscape-wide",
        "trackId": track_id,
        "split": "test",
        "targetRole": "target",
        "identityGroupId": identity,
        "framePath": "frame.jpg",
    }


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> Path:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def test_manifest_loader_collapses_frames_and_hashes_labels(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "manifest.jsonl", [_frame(), _frame()])

    references = load_track_references(path)

    assert len(references) == 1
    assert references[0].track_id == "track-a"
    assert references[0].frame_count == 2
    assert len(manifest_sha256(path)) == 64
    assert len(identity_label_sha256(references)) == 64


def test_manifest_loader_rejects_metadata_change_inside_track(tmp_path: Path) -> None:
    changed = _frame()
    changed["identityGroupId"] = "person-b"
    path = _write_jsonl(tmp_path / "manifest.jsonl", [_frame(), changed])

    with pytest.raises(CCTVDataError, match="metadata changes"):
        load_track_references(path)


def test_prediction_loader_rejects_unknown_shape(tmp_path: Path) -> None:
    path = _write_jsonl(tmp_path / "predictions.jsonl", [{"queryTrackId": "track-a"}])

    with pytest.raises(CCTVDataError, match="invalid track prediction"):
        load_track_predictions(path)
