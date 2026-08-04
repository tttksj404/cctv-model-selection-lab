from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Protocol, TypeAlias

import numpy as np
import torch
from PIL import Image

from qwen_backend.realtime_model_security import verified_solider_checkpoint
from qwen_backend.realtime_models import (
    ReferenceImageError,
    SoliderCheckoutError,
    SoliderFeatureError,
)
from qwen_backend.solider_runtime import SoliderImageEncoder

SOLIDER_COMMIT = "8c08e1c3255e8e1e51e006bf189e52cc57b009ed"
SOLIDER_REMOTE = "https://github.com/tinyvision/SOLIDER-REID.git"


class SoliderRuntimeConfig(Protocol):
    @property
    def device(self) -> str: ...

    @property
    def solider_checkpoint(self) -> str: ...

    @property
    def solider_root(self) -> str: ...

    @property
    def reference_image(self) -> Path | None: ...

    @property
    def model_directory(self) -> str: ...

    @property
    def model_manifest(self) -> str: ...


SoliderOutput: TypeAlias = tuple[torch.Tensor, ...]


def validate_reference_image(path: Path) -> Path:
    resolved = path.resolve()
    if not resolved.is_file():
        raise ReferenceImageError(resolved)
    try:
        with Image.open(resolved) as image:
            _ = image.tobytes()
    except OSError as error:
        raise ReferenceImageError(resolved) from error
    return resolved


def _git_output(root: Path, *arguments: str) -> str:
    git_executable = shutil.which("git")
    if git_executable is None:
        raise FileNotFoundError("git executable not found")
    result = subprocess.run(
        (
            git_executable,
            "-c",
            "core.fsmonitor=false",
            "-c",
            "core.hooksPath=NUL",
            "-c",
            "core.untrackedCache=false",
            "-C",
            str(root),
            *arguments,
        ),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_TERMINAL_PROMPT": "0",
            "PATH": os.environ.get("PATH", ""),
        },
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or "git command failed"
        raise SoliderCheckoutError(root, detail)
    return result.stdout.strip()


def verified_solider_root(candidate: str) -> Path:
    root = Path(candidate).resolve()
    if not root.is_dir():
        raise SoliderCheckoutError(root, "checkout directory missing")
    actual_commit = _git_output(root, "rev-parse", "--verify", "HEAD^{commit}")
    if actual_commit != SOLIDER_COMMIT:
        raise SoliderCheckoutError(
            root,
            f"expected commit {SOLIDER_COMMIT}, actual {actual_commit}",
        )
    remote = _git_output(root, "remote", "get-url", "origin")
    if remote != SOLIDER_REMOTE:
        raise SoliderCheckoutError(root, f"unexpected origin {remote}")
    status = _git_output(
        root,
        "status",
        "--porcelain=v1",
        "--untracked-files=all",
    )
    if status:
        raise SoliderCheckoutError(root, f"working tree is not clean: {status.splitlines()[0]}")
    expected_config = root / "configs" / "msmt17" / "swin_base.yml"
    if not expected_config.is_file():
        raise SoliderCheckoutError(root, "runtime config missing")
    return root


def _solider_feature(output: SoliderOutput) -> torch.Tensor:
    if not output:
        raise SoliderFeatureError
    return output[0]


class SoliderIdentityScorer:
    def __init__(self, config: SoliderRuntimeConfig) -> None:
        root = verified_solider_root(config.solider_root)
        reference_path = (
            validate_reference_image(config.reference_image)
            if config.reference_image is not None
            else None
        )
        sys.dont_write_bytecode = True
        checkpoint = verified_solider_checkpoint(config)
        self._encoder = SoliderImageEncoder(
            device=torch.device(config.device),
            checkpoint=checkpoint,
            root=root,
        )
        self._anchor: torch.Tensor | None = None
        self._reference_mode = reference_path is not None
        if reference_path is not None:
            with Image.open(reference_path) as image:
                self._anchor = self._encode_pil(image.convert("RGB"))

    @property
    def has_anchor(self) -> bool:
        return self._anchor is not None

    @property
    def mode_label(self) -> str:
        if self._reference_mode and self.has_anchor:
            return "SOLIDER 기준사진 동일인 검증"
        if self.has_anchor:
            return "SOLIDER 최초후보 자동등록·추적"
        return "SOLIDER 자동등록 대기"

    def _encode_pil(self, image: Image.Image) -> torch.Tensor:
        tensor = self._encoder.processor(image).unsqueeze(0).to(self._encoder.device)
        with torch.inference_mode():
            feature = _solider_feature(self._encoder.model(tensor))
            flipped = _solider_feature(
                self._encoder.model(torch.flip(tensor, dims=(3,)))
            )
            combined = torch.nn.functional.normalize(
                feature, dim=-1
            ) + torch.nn.functional.normalize(flipped, dim=-1)
            return torch.nn.functional.normalize(combined, dim=-1)[0].detach()

    def encode_crop(self, crop_bgr: np.ndarray) -> torch.Tensor:
        rgb = np.ascontiguousarray(crop_bgr[:, :, ::-1])
        with Image.fromarray(rgb) as image:
            return self._encode_pil(image)

    def enroll(self, crop_bgr: np.ndarray) -> None:
        if self.has_anchor:
            return
        self._anchor = self.encode_crop(crop_bgr)

    def similarity(self, crop_bgr: np.ndarray) -> float | None:
        if self._anchor is None:
            return None
        feature = self.encode_crop(crop_bgr)
        cosine = float(torch.dot(feature, self._anchor).float().cpu())
        return min(1.0, max(0.0, (cosine + 1.0) / 2.0))
