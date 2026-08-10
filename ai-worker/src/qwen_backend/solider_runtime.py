from __future__ import annotations

import collections.abc
import importlib
import sys
import types
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image


class SoliderRuntimeLoadError(RuntimeError):
    pass


class _ModelSettings(Protocol):
    PRETRAIN_PATH: str
    PRETRAIN_CHOICE: str


class _TestSettings(Protocol):
    NECK_FEAT: str


class _InputSettings(Protocol):
    SIZE_TEST: list[int]
    PIXEL_MEAN: list[float]
    PIXEL_STD: list[float]


class _SoliderConfig(Protocol):
    MODEL: _ModelSettings
    TEST: _TestSettings
    INPUT: _InputSettings

    def clone(self) -> _SoliderConfig: ...

    def merge_from_file(self, config_path: str) -> None: ...

    def freeze(self) -> None: ...


class _SoliderModel(Protocol):
    def __call__(self, inputs: torch.Tensor) -> tuple[torch.Tensor, ...]: ...

    def load_param(self, trained_path: str) -> None: ...

    def load_state_dict(
        self,
        state_dict: Mapping[str, torch.Tensor],
        *,
        strict: bool = False,
    ) -> None: ...

    def to(self, device: torch.device) -> _SoliderModel: ...

    def eval(self) -> _SoliderModel: ...


class _MakeModel(Protocol):
    def __call__(
        self,
        config: _SoliderConfig,
        *,
        num_class: int,
        camera_num: int,
        view_num: int,
        semantic_weight: float,
    ) -> _SoliderModel: ...


class _ImageProcessor(Protocol):
    def __call__(self, image: Image.Image) -> torch.Tensor: ...


CheckpointPayload = (
    dict[str, torch.Tensor] | dict[str, Mapping[str, torch.Tensor]]
)


def _load_checkpoint(
    model: _SoliderModel,
    filename: str,
    map_location: str | torch.device | None = None,
    strict: bool = False,
    logger: Callable[[str], None] | None = None,
) -> CheckpointPayload:
    del logger
    payload = cast(
        CheckpointPayload,
        torch.load(filename, map_location=map_location, weights_only=False),
    )
    nested_state = payload.get("state_dict")
    state_dict = (
        nested_state
        if isinstance(nested_state, Mapping)
        else cast(Mapping[str, torch.Tensor], payload)
    )
    _ = model.load_state_dict(state_dict, strict=strict)
    return payload


def _install_torch_six_compat() -> None:
    if "torch._six" in sys.modules:
        return
    compatibility_module = types.ModuleType("torch._six")
    compatibility_module.__dict__["container_abcs"] = collections.abc
    sys.modules["torch._six"] = compatibility_module


def _install_mmcv_runner_compat() -> None:
    try:
        _ = importlib.import_module("mmcv.runner")
    except ModuleNotFoundError as error:
        if error.name not in {"mmcv", "mmcv.runner"}:
            raise
    else:
        return

    try:
        mmcv_module = importlib.import_module("mmcv")
    except ModuleNotFoundError:
        mmcv_module = types.ModuleType("mmcv")
        sys.modules["mmcv"] = mmcv_module
    runner_module = types.ModuleType("mmcv.runner")
    runner_module.__dict__["load_checkpoint"] = _load_checkpoint
    mmcv_module.__dict__["runner"] = runner_module
    sys.modules["mmcv.runner"] = runner_module


def _verified_module(module_name: str, root: Path) -> types.ModuleType:
    module = importlib.import_module(module_name)
    module_file = getattr(module, "__file__", None)
    if not isinstance(module_file, str):
        raise SoliderRuntimeLoadError(f"SOLIDER module has no source path: {module_name}")
    if not Path(module_file).resolve().is_relative_to(root):
        raise SoliderRuntimeLoadError(
            f"SOLIDER module resolved outside verified checkout: {module_name}"
        )
    return module


class SoliderImageEncoder:
    device: torch.device
    processor: _ImageProcessor
    model: _SoliderModel

    def __init__(
        self,
        *,
        device: torch.device,
        checkpoint: str,
        root: Path,
    ) -> None:
        config_path = root / "configs" / "msmt17" / "swin_base.yml"
        if not config_path.is_file():
            raise SoliderRuntimeLoadError(f"SOLIDER config not found: {config_path}")
        if str(root) not in sys.path:
            sys.path.insert(0, str(root))
        _install_torch_six_compat()
        _install_mmcv_runner_compat()

        config_module = _verified_module("config", root)
        model_module = _verified_module("model", root)
        base_config = cast(_SoliderConfig, config_module.__dict__["cfg"])
        make_model = cast(_MakeModel, model_module.__dict__["make_model"])

        config = base_config.clone()
        config.merge_from_file(str(config_path))
        config.MODEL.PRETRAIN_PATH = ""
        config.MODEL.PRETRAIN_CHOICE = "finetune"
        config.TEST.NECK_FEAT = "before"
        config.freeze()

        height, width = config.INPUT.SIZE_TEST
        mean = torch.tensor(config.INPUT.PIXEL_MEAN, dtype=torch.float32).view(3, 1, 1)
        standard_deviation = torch.tensor(
            config.INPUT.PIXEL_STD,
            dtype=torch.float32,
        ).view(3, 1, 1)

        def process_image(image: Image.Image) -> torch.Tensor:
            resized = image.resize((width, height), Image.Resampling.BICUBIC)
            pixels: NDArray[np.float32] = np.asarray(
                resized.convert("RGB"),
                dtype=np.float32,
            )
            pixels /= np.float32(255.0)
            tensor = torch.tensor(pixels, dtype=torch.float32).permute(2, 0, 1)
            return (tensor - mean) / standard_deviation

        self.device = device
        self.processor = process_image
        model = make_model(
            config,
            num_class=1,
            camera_num=0,
            view_num=0,
            semantic_weight=0.2,
        )
        model.load_param(checkpoint)
        self.model = model.to(device).eval()

