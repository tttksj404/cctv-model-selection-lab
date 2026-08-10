from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal, Protocol, overload

import numpy as np
import torch
from numpy.typing import NDArray
from PIL import Image
from transformers import CLIPModel

from qwen_backend.realtime_models import AttributeEvidence


class ClipProcessor(Protocol):
    @overload
    def __call__(
        self,
        *,
        text: Sequence[str],
        return_tensors: Literal["pt"],
        padding: bool,
    ) -> Mapping[str, torch.Tensor]: ...

    @overload
    def __call__(
        self,
        *,
        images: Sequence[Image.Image],
        return_tensors: Literal["pt"],
    ) -> Mapping[str, torch.Tensor]: ...


class ProcessorFactory(Protocol):
    @staticmethod
    def from_pretrained(
        pretrained_model_name_or_path: str,
        *,
        revision: str,
        local_files_only: bool,
        use_fast: bool,
    ) -> ClipProcessor: ...


class ClipModelFactory(Protocol):
    @staticmethod
    def from_pretrained(
        pretrained_model_name_or_path: str,
        *,
        revision: str,
        dtype: torch.dtype,
        local_files_only: bool,
        use_safetensors: bool,
    ) -> CLIPModel: ...


class Boxes(Protocol):
    @property
    def id(self) -> torch.Tensor | None: ...

    @property
    def xyxy(self) -> torch.Tensor: ...

    @property
    def conf(self) -> torch.Tensor: ...


class TrackingResult(Protocol):
    @property
    def boxes(self) -> Boxes | None: ...


class Detector(Protocol):
    def track(
        self,
        *,
        source: NDArray[np.uint8],
        persist: bool,
        classes: list[int],
        conf: float,
        imgsz: int,
        tracker: str,
        device: str,
        verbose: bool,
    ) -> Sequence[TrackingResult]: ...


class AttributeScorer(Protocol):
    def score(self, crop_bgr: NDArray[np.uint8]) -> AttributeEvidence: ...


class IdentityScorer(Protocol):
    @property
    def has_anchor(self) -> bool: ...

    @property
    def mode_label(self) -> str: ...

    def enroll(self, crop_bgr: NDArray[np.uint8]) -> None: ...

    def similarity(self, crop_bgr: NDArray[np.uint8]) -> float | None: ...

