from pathlib import Path


def test_training_guide_is_utf8_and_contains_run_commands() -> None:
    guide = Path("docs/DISTILLATION_TRAINING_GUIDE.md").read_text(encoding="utf-8")
    assert "Qwen3-VL" in guide
    assert "Sonnet" in guide
    assert "DRY_RUN=0" in guide
    assert "build_geometry_manifest.py" in guide

