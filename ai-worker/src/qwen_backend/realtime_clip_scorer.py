from __future__ import annotations

from typing import Protocol, cast

import numpy as np
import torch
from PIL import Image
from transformers import AutoProcessor, CLIPModel

from qwen_backend.clip_features import pooled_clip_features
from qwen_backend.realtime_color_scoring import color_match_score
from qwen_backend.realtime_models import AppearanceProfile, AttributeEvidence
from qwen_backend.realtime_protocols import ClipModelFactory, ProcessorFactory


class ClipRuntimeConfig(Protocol):
    @property
    def clip_checkpoint(self) -> str: ...

    @property
    def clip_revision(self) -> str: ...

    @property
    def device(self) -> str: ...


class ClipAttributeScorer:
    def __init__(
        self,
        profile: AppearanceProfile,
        config: ClipRuntimeConfig,
    ) -> None:
        self._profile = profile
        self._device = torch.device(config.device)
        processor_factory = cast(ProcessorFactory, AutoProcessor)
        self._processor = processor_factory.from_pretrained(
            config.clip_checkpoint,
            revision=config.clip_revision,
            local_files_only=True,
            use_fast=False,
        )
        model_factory = cast(ClipModelFactory, CLIPModel)
        model = model_factory.from_pretrained(
            config.clip_checkpoint,
            revision=config.clip_revision,
            dtype=torch.float16,
            local_files_only=True,
            use_safetensors=True,
        )
        self._model = cast(
            CLIPModel,
            torch.nn.Module.to(model, device=self._device),
        ).eval()
        prompts = (
            profile.clip_query_en,
            profile.exclusion_query_en,
            profile.glasses_positive_en,
            profile.glasses_negative_en,
            profile.hair_positive_en,
            profile.hair_negative_en,
            profile.upper_style_positive_en,
            profile.upper_style_negative_en,
        )
        text_inputs = self._processor(text=prompts, return_tensors="pt", padding=True)
        text_inputs = {
            name: value.to(self._device) for name, value in text_inputs.items()
        }
        with torch.inference_mode():
            features = pooled_clip_features(self._model.get_text_features(**text_inputs))
            self._text_features = torch.nn.functional.normalize(features, dim=-1)
            self._logit_scale = self._model.logit_scale.exp().clamp(max=100.0)

    @staticmethod
    def _regions(crop_bgr: np.ndarray) -> tuple[np.ndarray, ...]:
        height, width = crop_bgr.shape[:2]
        head = crop_bgr[
            : max(1, round(height * 0.36)),
            round(width * 0.16) : max(round(width * 0.84), 1),
        ]
        upper = crop_bgr[
            round(height * 0.18) : max(round(height * 0.62), 1),
            round(width * 0.10) : max(round(width * 0.90), 1),
        ]
        lower = crop_bgr[
            round(height * 0.52) : max(round(height * 0.98), 1),
            round(width * 0.16) : max(round(width * 0.84), 1),
        ]
        return crop_bgr, head, upper, lower

    def score(self, crop_bgr: np.ndarray) -> AttributeEvidence:
        full, head, upper, lower = self._regions(crop_bgr)
        height, width = crop_bgr.shape[:2]
        pants_are_visible = height >= width * 1.3
        images = [
            Image.fromarray(np.ascontiguousarray(region[:, :, ::-1]))
            for region in (full, head, upper)
        ]
        try:
            image_inputs = self._processor(images=images, return_tensors="pt")
        finally:
            for image in images:
                image.close()
        pixel_values = image_inputs["pixel_values"].to(
            self._device,
            dtype=self._model.dtype,
        )
        with torch.inference_mode():
            features = pooled_clip_features(
                self._model.get_image_features(
                    pixel_values=cast(torch.FloatTensor, pixel_values)
                )
            )
            image_features = torch.nn.functional.normalize(features, dim=-1)
            logits = self._logit_scale * image_features @ self._text_features.T

        def pair_score(image_index: int, positive: int, negative: int) -> float:
            pair = logits[image_index, [positive, negative]].float()
            return float(torch.softmax(pair, dim=0)[0].cpu())

        return AttributeEvidence(
            top_color=(
                color_match_score(upper, target=self._profile.top_color_target)
                if self._profile.top_color_target is not None
                else None
            ),
            bottom_color=(
                color_match_score(lower, target=self._profile.bottom_color_target)
                if pants_are_visible and self._profile.bottom_color_target is not None
                else None
            ),
            glasses=(
                pair_score(1, 2, 3)
                if self._profile.requirements.glasses
                else None
            ),
            hair=(
                pair_score(1, 4, 5) if self._profile.requirements.hair else None
            ),
            upper_style=(
                pair_score(2, 6, 7)
                if self._profile.requirements.upper_style
                else None
            ),
            holistic=pair_score(0, 0, 1),
        )

