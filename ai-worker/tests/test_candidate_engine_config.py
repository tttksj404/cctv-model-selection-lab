from pathlib import Path

import pytest
from pydantic import ValidationError

from qwen_backend.solider_clip_engine import EngineConfig


def test_candidate_engine_config_reads_all_runtime_thresholds_from_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_CANDIDATE_MODEL_KEY", "fixture-v2")
    monkeypatch.setenv("QWEN_CANDIDATE_DEVICE", "cpu")
    monkeypatch.setenv("QWEN_CANDIDATE_DETECTOR_CONFIDENCE", "0.41")
    monkeypatch.setenv("QWEN_CANDIDATE_FRAME_STRIDE", "2")
    monkeypatch.setenv("QWEN_CANDIDATE_SAMPLE_EVERY_SECONDS", "1.25")
    monkeypatch.setenv("QWEN_CANDIDATE_CROP_MARGIN", "0.12")
    monkeypatch.setenv("QWEN_CANDIDATE_MIN_PERSON_CROP_QUALITY", "0.55")
    monkeypatch.setenv("QWEN_CANDIDATE_REID_WEIGHT", "0.6")
    monkeypatch.setenv("QWEN_CANDIDATE_CLIP_WEIGHT", "0.4")
    monkeypatch.setenv("QWEN_CANDIDATE_AGGREGATE_TOP_FRAMES", "5")
    monkeypatch.setenv("QWEN_CANDIDATE_IDENTITY_PRIMARY_RETRIEVAL", "true")
    monkeypatch.setenv("QWEN_CANDIDATE_REID_BATCH_SIZE", "16")

    config = EngineConfig.from_environment()

    assert config.model_key == "fixture-v2"
    assert config.device == "cpu"
    assert config.detector_confidence == 0.41
    assert config.frame_stride == 2
    assert config.sample_every_seconds == 1.25
    assert config.crop_margin == 0.12
    assert config.minimum_person_crop_quality == 0.55
    assert config.reid_weight == 0.6
    assert config.clip_weight == 0.4
    assert config.aggregate_top_frames == 5
    assert config.identity_primary_retrieval is True
    assert config.reid_batch_size == 16


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("QWEN_CANDIDATE_DETECTOR_CONFIDENCE", "1.1"),
        ("QWEN_CANDIDATE_FRAME_STRIDE", "0"),
        ("QWEN_CANDIDATE_SAMPLE_EVERY_SECONDS", "0"),
        ("QWEN_CANDIDATE_CROP_MARGIN", "0.51"),
        ("QWEN_CANDIDATE_MIN_PERSON_CROP_QUALITY", "1.1"),
        ("QWEN_CANDIDATE_TOP_K", "0"),
        ("QWEN_CANDIDATE_REID_BATCH_SIZE", "0"),
    ],
)
def test_candidate_engine_config_rejects_invalid_runtime_limits(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        EngineConfig.from_environment()


def test_candidate_engine_config_requires_a_non_zero_combined_weight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_CANDIDATE_REID_WEIGHT", "0")
    monkeypatch.setenv("QWEN_CANDIDATE_CLIP_WEIGHT", "0")

    with pytest.raises(ValidationError, match="scoring weights"):
        EngineConfig.from_environment()


def test_candidate_engine_config_accepts_local_model_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "reid.pth"
    monkeypatch.setenv("QWEN_CANDIDATE_REID_CHECKPOINT", str(checkpoint))
    monkeypatch.setenv("SOLIDER_REID_ROOT", str(tmp_path / "SOLIDER-REID"))

    config = EngineConfig.from_environment()

    assert config.reid_checkpoint == checkpoint
    assert config.solider_root == tmp_path / "SOLIDER-REID"


def test_candidate_engine_config_reads_remote_qwen_review_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_CANDIDATE_QWEN_REVIEW_PROVIDER", "remote")
    monkeypatch.setenv("QWEN_CANDIDATE_QWEN_REMOTE_BASE_URL", "http://gpu.example:8000/v1")
    monkeypatch.setenv("QWEN_CANDIDATE_QWEN_REMOTE_MODEL", "qwen-active")
    monkeypatch.setenv("QWEN_CANDIDATE_QWEN_REMOTE_API_KEY", "test-key")
    monkeypatch.setenv("QWEN_CANDIDATE_QWEN_REMOTE_TIMEOUT_SECONDS", "45")

    config = EngineConfig.from_environment()

    assert config.qwen_review_provider == "remote"
    assert config.qwen_remote_base_url == "http://gpu.example:8000/v1"
    assert config.qwen_remote_model == "qwen-active"
    assert config.qwen_remote_api_key == "test-key"
    assert config.qwen_remote_timeout_seconds == 45.0
