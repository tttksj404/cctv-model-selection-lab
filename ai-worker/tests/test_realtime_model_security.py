import hashlib
import json
from pathlib import Path

import pytest

from qwen_backend.realtime_model_security import ModelWeightError, verified_yolo_weights
from qwen_backend.realtime_vision import RealtimeVisionConfig


def test_clip_revision_is_pinned_to_immutable_commit() -> None:
    config = RealtimeVisionConfig()

    assert config.clip_revision == "32bd64288804d66eefd0ccbe215aa642df71cc41"
    assert len(config.clip_revision) == 40


def _write_manifest(path: Path, model_name: str, sha256: str) -> None:
    path.write_text(
        json.dumps({"models": {model_name: {"sha256": sha256}}}),
        encoding="utf-8",
    )


def test_verified_yolo_weights_accepts_manifested_local_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    model_directory = tmp_path / "models"
    model_directory.mkdir()
    weights_path = model_directory / "yolo11n.pt"
    weights_path.write_bytes(b"trusted test checkpoint")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(
        manifest_path,
        weights_path.name,
        hashlib.sha256(weights_path.read_bytes()).hexdigest(),
    )
    config = RealtimeVisionConfig(
        yolo_weights="models/yolo11n.pt",
        model_manifest=manifest_path.name,
    )

    verified = verified_yolo_weights(config)

    assert verified == str(weights_path.resolve())


def test_verified_yolo_weights_rejects_file_outside_model_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    outside = tmp_path / "outside.pt"
    outside.write_bytes(b"untrusted")
    config = RealtimeVisionConfig(yolo_weights=str(outside))

    with pytest.raises(ModelWeightError, match="outside_trusted_model_directory"):
        verified_yolo_weights(config)


def test_verified_yolo_weights_rejects_hash_mismatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    model_directory = tmp_path / "models"
    model_directory.mkdir()
    weights_path = model_directory / "yolo11n.pt"
    weights_path.write_bytes(b"tampered")
    manifest_path = tmp_path / "manifest.json"
    _write_manifest(manifest_path, weights_path.name, "0" * 64)
    config = RealtimeVisionConfig(
        yolo_weights="models/yolo11n.pt",
        model_manifest=manifest_path.name,
    )

    with pytest.raises(ModelWeightError, match="sha256_mismatch"):
        verified_yolo_weights(config)
