from __future__ import annotations

from typing import Protocol

import torch


class ClipVisionOutput(Protocol):
    @property
    def pooler_output(self) -> torch.Tensor | str | None: ...


class ClipFeatureTypeError(TypeError):
    pass


def pooled_clip_features(
    output: torch.Tensor | ClipVisionOutput,
) -> torch.Tensor:
    if isinstance(output, torch.Tensor):
        return output
    pooled_output = output.pooler_output
    if not isinstance(pooled_output, torch.Tensor):
        raise ClipFeatureTypeError("CLIP pooler_output must be a torch.Tensor")
    return pooled_output
