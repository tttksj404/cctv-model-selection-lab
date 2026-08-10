from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import torch
from PIL import Image

from qwen_backend.video_tracks import TrackFrame

_IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


class HistoricalRetrievalRuntime:
    """Optional local gallery retrieval for previously observed target crops.

    The gallery is deliberately opt-in.  A missing gallery is reported as
    unavailable instead of replacing identity evidence with a prompt score.
    This prevents a historical ranking signal from being mistaken for a
    calibrated same-person probability.
    """

    def __init__(
        self,
        gallery_directory: Path | None,
        device: str,
        *,
        max_images: int = 512,
    ) -> None:
        self._gallery_directory = gallery_directory
        self._device = device
        self._max_images = max_images
        self._cached_paths: tuple[Path, ...] = ()
        self._cached_signature: tuple[tuple[str, int], ...] = ()
        self._cached_features: torch.Tensor | None = None

    def score(
        self,
        frames: Sequence[TrackFrame],
        *,
        case_id: int,
        identity_anchor: Path | None,
        bundle: Any,
    ) -> tuple[dict[int, float], str]:
        if self._gallery_directory is None:
            return {}, "unavailable:not_configured"
        if identity_anchor is None:
            return {}, "skipped:no_identity_anchor"
        gallery = self._resolve_gallery(case_id)
        if not gallery:
            return {}, "unavailable:empty_gallery"
        try:
            gallery_features = self._gallery_features(gallery, bundle)
            anchor_features = _image_features(bundle, (identity_anchor,), self._device)
            anchor_similarity = ((anchor_features @ gallery_features.T) + 1.0) / 2.0
            gallery_count = min(8, len(gallery))
            selected_indices = torch.topk(
                anchor_similarity[0], k=gallery_count, largest=True
            ).indices
            selected_gallery_features = gallery_features[selected_indices]
            frame_features = _image_features(
                bundle,
                tuple(frame.crop_path for frame in frames),
                self._device,
            )
            similarities = ((frame_features @ selected_gallery_features.T) + 1.0) / 2.0
            grouped: dict[int, list[float]] = {}
            for index, frame in enumerate(frames):
                grouped.setdefault(frame.track_id, []).append(
                    float(similarities[index].max().item())
                )
            return {
                track_id: max(0.0, min(1.0, sum(values) / len(values)))
                for track_id, values in grouped.items()
                if values
            }, f"used:clip_gallery_top{gallery_count}"
        except (OSError, RuntimeError, TypeError, ValueError) as error:
            return {}, f"failed:{type(error).__name__}"

    def _resolve_gallery(self, case_id: int) -> tuple[Path, ...]:
        assert self._gallery_directory is not None
        root = self._gallery_directory.expanduser().resolve()
        candidates = (root / f"case-{case_id}", root / str(case_id), root)
        selected_root = next((path for path in candidates if path.is_dir()), None)
        if selected_root is None:
            return ()
        paths = tuple(
            path
            for path in sorted(selected_root.rglob("*"))
            if path.is_file() and path.suffix.lower() in _IMAGE_SUFFIXES
        )
        return paths[: self._max_images]

    def _gallery_features(self, paths: tuple[Path, ...], bundle: Any) -> torch.Tensor:
        signature = tuple((str(path), path.stat().st_mtime_ns) for path in paths)
        if signature == self._cached_signature and self._cached_features is not None:
            return self._cached_features
        features = _image_features(bundle, paths, self._device)
        self._cached_paths = paths
        self._cached_signature = signature
        self._cached_features = features
        return features


def _image_features(
    bundle: Any,
    paths: Sequence[Path],
    device: str,
    *,
    batch_size: int = 32,
) -> torch.Tensor:
    outputs: list[torch.Tensor] = []
    for start in range(0, len(paths), batch_size):
        images: list[Image.Image] = []
        try:
            for path in paths[start : start + batch_size]:
                with Image.open(path) as source:
                    images.append(source.convert("RGB"))
            inputs = bundle.processor(images=images, return_tensors="pt")
            pixel_values = inputs["pixel_values"].to(device, dtype=bundle.model.dtype)
            with torch.inference_mode():
                features = bundle.model.get_image_features(pixel_values=pixel_values)
            outputs.append(torch.nn.functional.normalize(features, dim=-1).float().cpu())
        finally:
            for image in images:
                image.close()
    if not outputs:
        raise ValueError("historical gallery contains no readable images")
    return torch.cat(outputs, dim=0)

