from types import SimpleNamespace
from typing import cast

import pytest
import torch

from qwen_backend.clip_features import ClipVisionOutput, pooled_clip_features


def test_pooled_clip_features_accepts_legacy_tensor_output() -> None:
    # Given: Transformers 4 style CLIP output.
    expected = torch.tensor([[1.0, 2.0]])

    # When: the compatibility adapter reads the output.
    actual = pooled_clip_features(expected)

    # Then: the existing tensor is returned without modification.
    assert actual is expected


def test_pooled_clip_features_accepts_transformers_5_model_output() -> None:
    # Given: Transformers 5 style output with projected features in pooler_output.
    expected = torch.tensor([[3.0, 4.0]])
    output = cast(ClipVisionOutput, SimpleNamespace(pooler_output=expected))

    # When: the compatibility adapter reads the output.
    actual = pooled_clip_features(output)

    # Then: the projected pooled tensor is returned.
    assert actual is expected


def test_pooled_clip_features_rejects_non_tensor_pooler_output() -> None:
    # Given: an incompatible model output.
    output = cast(ClipVisionOutput, SimpleNamespace(pooler_output="not-a-tensor"))

    # When / Then: the boundary fails closed.
    with pytest.raises(TypeError, match=r"torch\.Tensor"):
        pooled_clip_features(output)

