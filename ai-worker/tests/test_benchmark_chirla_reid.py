import collections.abc
import sys
import types
from pathlib import Path

import pytest

from scripts.benchmark_chirla_support import (
    LegacyCompatibilityDisabledError,
    _family,
    _install_mmcv_runner_compat,
    _install_torch_six_compat,
    _require_local_checkpoint,
    _resolve_model_root,
)


def test_solider_reid_family_is_detected() -> None:
    assert _family("solider-reid-swin-base-msmt17") == "solider"


def test_solider_reid_legacy_torch_import_is_supported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "torch._six", raising=False)

    _install_torch_six_compat()

    assert sys.modules["torch._six"].__dict__["container_abcs"] is collections.abc


def test_solider_reid_mmcv_fallback_is_disabled_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "mmcv", raising=False)
    monkeypatch.delitem(sys.modules, "mmcv.runner", raising=False)
    monkeypatch.delenv("QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT", raising=False)

    with pytest.raises(LegacyCompatibilityDisabledError, match="compatibility is disabled"):
        _install_mmcv_runner_compat()


def test_solider_reid_mmcv_fallback_requires_explicit_opt_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delitem(sys.modules, "mmcv", raising=False)
    monkeypatch.delitem(sys.modules, "mmcv.runner", raising=False)
    monkeypatch.setenv("QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT", "1")

    _install_mmcv_runner_compat()

    assert callable(sys.modules["mmcv.runner"].__dict__["load_checkpoint"])


def test_solider_reid_preserves_installed_mmcv_runner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mmcv_module = types.ModuleType("mmcv")
    runner_module = types.ModuleType("mmcv.runner")

    def installed_load_checkpoint() -> str:
        return "installed"

    runner_module.__dict__["load_checkpoint"] = installed_load_checkpoint
    mmcv_module.__dict__["runner"] = runner_module
    monkeypatch.setitem(sys.modules, "mmcv", mmcv_module)
    monkeypatch.setitem(sys.modules, "mmcv.runner", runner_module)
    monkeypatch.delenv("QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT", raising=False)

    _install_mmcv_runner_compat()

    assert (
        sys.modules["mmcv.runner"].__dict__["load_checkpoint"]
        is installed_load_checkpoint
    )


def test_model_root_must_contain_expected_package(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="model package directory"):
        _resolve_model_root(tmp_path, "model")


def test_local_checkpoint_must_exist(tmp_path: Path) -> None:
    missing = tmp_path / "missing.pth"

    with pytest.raises(FileNotFoundError, match="local verified"):
        _require_local_checkpoint(str(missing), "SOLIDER-ReID")

