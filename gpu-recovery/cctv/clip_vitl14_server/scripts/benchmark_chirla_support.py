from __future__ import annotations

import collections.abc
import hashlib
import os
import sys
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    import torch

ModelFamily = Literal[
    "clip",
    "clipreid",
    "siglip2",
    "generic",
    "reid",
    "fastreid",
    "solider",
]


class LegacyCompatibilityDisabledError(RuntimeError):
    pass


class ManifestIntegrityError(ValueError):
    pass


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_matching_sha256(path: Path, expected_sha256: str, label: str) -> str:
    normalized_expected = expected_sha256.lower()
    if _file_sha256(path) != normalized_expected:
        raise ManifestIntegrityError(f"manifest image hash mismatch for {label}")
    return normalized_expected


def _resolve_model_root(root: Path, package_directory: str) -> Path:
    resolved = root.resolve()
    if not (resolved / package_directory).is_dir():
        raise FileNotFoundError(
            f"model package directory not found: {resolved / package_directory}"
        )
    return resolved


def _require_local_checkpoint(checkpoint: str, model_label: str) -> Path:
    weights = Path(checkpoint)
    if not weights.is_file():
        raise FileNotFoundError(
            f"{model_label} checkpoint must be a local verified .pth file: {weights}"
        )
    return weights.resolve()


def _install_torch_six_compat() -> None:
    if "torch._six" in sys.modules:
        return
    compatibility_module = types.ModuleType("torch._six")
    compatibility_module.__dict__["container_abcs"] = collections.abc
    sys.modules["torch._six"] = compatibility_module


def _install_mmcv_runner_compat() -> None:
    try:
        from mmcv.runner import load_checkpoint as installed_load_checkpoint
    except ModuleNotFoundError as exc:
        if exc.name not in {"mmcv", "mmcv.runner"}:
            raise
    else:
        del installed_load_checkpoint
        return
    if os.environ.get("QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT") != "1":
        raise LegacyCompatibilityDisabledError(
            "legacy SOLIDER mmcv.runner compatibility is disabled; "
            "set QWEN_ENABLE_LEGACY_MMCV_RUNNER_COMPAT=1 for the audited fallback"
        )

    def load_checkpoint(
        model: torch.nn.Module,
        filename: str,
        map_location: str | torch.device | None = None,
        strict: bool = False,
        logger: Any | None = None,
    ) -> Any:
        import torch

        del logger
        checkpoint = torch.load(
            filename,
            map_location=map_location,
            weights_only=True,
        )
        state_dict = (
            checkpoint.get("state_dict", checkpoint)
            if isinstance(checkpoint, dict)
            else checkpoint
        )
        model.load_state_dict(state_dict, strict=strict)
        return checkpoint

    try:
        import mmcv as mmcv_module
    except ModuleNotFoundError:
        mmcv_module = types.ModuleType("mmcv")
        sys.modules["mmcv"] = mmcv_module
    runner_module = types.ModuleType("mmcv.runner")
    runner_module.__dict__["load_checkpoint"] = load_checkpoint
    mmcv_module.__dict__["runner"] = runner_module
    sys.modules["mmcv.runner"] = runner_module


def _family(model_name: str) -> ModelFamily:
    if model_name.startswith("clip-"):
        return "clip"
    if model_name.startswith("clipreid-"):
        return "clipreid"
    if model_name.startswith("siglip2-"):
        return "siglip2"
    if model_name.startswith("osnet-"):
        return "reid"
    if model_name.startswith("fastreid-"):
        return "fastreid"
    if model_name.startswith("solider-reid-"):
        return "solider"
    return "generic"
