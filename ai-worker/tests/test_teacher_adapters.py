from pathlib import Path

import pytest

from qwen_backend.teacher_adapters import TeacherAdapterError, build_teacher_adapter


def test_manifest_adapter_is_explicit() -> None:
    adapter = build_teacher_adapter("manifest")
    assert adapter.__class__.__name__ == "ManifestTeacherAdapter"


def test_unknown_teacher_mode_is_rejected() -> None:
    with pytest.raises(TeacherAdapterError, match="unsupported teacher mode"):
        build_teacher_adapter("clip")


def test_manifest_cli_wrapper_imports() -> None:
    assert Path("scripts/build_geometry_manifest.py").is_file()
