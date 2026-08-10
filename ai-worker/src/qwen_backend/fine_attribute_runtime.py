from __future__ import annotations

import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import torch
from PIL import Image

from qwen_backend.clip_features import pooled_clip_features
from qwen_backend.video_tracks import TrackFrame

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FineHead:
    model: torch.nn.Module
    attributes: tuple[str, ...]
    thresholds: tuple[float, ...]
    checkpoint: str
    revision: str


def _load_head(path: Path, device: torch.device) -> FineHead:
    payload = cast(object, torch.load(path, map_location="cpu", weights_only=True))
    if not isinstance(payload, dict):
        raise ValueError("fine attribute checkpoint must contain a mapping")
    raw = cast(dict[str, object], payload)
    required = {"checkpoint", "revision", "architecture", "attributes", "thresholds", "stateDict"}
    if not required.issubset(raw):
        missing = sorted(required - raw.keys())
        raise ValueError(f"fine attribute checkpoint is missing fields: {missing}")
    attributes_value = raw["attributes"]
    thresholds_value = raw["thresholds"]
    state_value = raw["stateDict"]
    if not isinstance(attributes_value, (list, tuple)):
        raise ValueError("fine attribute names are invalid")
    if not isinstance(thresholds_value, (list, tuple)):
        raise ValueError("fine attribute thresholds are invalid")
    attribute_items = cast(list[object] | tuple[object, ...], attributes_value)
    threshold_items = cast(list[object] | tuple[object, ...], thresholds_value)
    if not all(isinstance(value, str) for value in attribute_items):
        raise ValueError("fine attribute names are invalid")
    if not all(isinstance(value, (int, float)) for value in threshold_items):
        raise ValueError("fine attribute thresholds are invalid")
    attributes = tuple(value for value in attribute_items if isinstance(value, str))
    thresholds = tuple(
        float(value) for value in threshold_items if isinstance(value, (int, float))
    )
    if not attributes or len(attributes) != len(thresholds):
        raise ValueError("fine attribute names and thresholds must have equal non-zero length")
    if not all(0.0 < value < 1.0 for value in thresholds):
        raise ValueError("fine attribute thresholds must be in (0, 1)")
    if not isinstance(state_value, dict):
        raise ValueError("fine attribute stateDict is invalid")
    state = cast(dict[str, torch.Tensor], state_value)
    architecture = raw["architecture"]
    if architecture == "linear":
        weight = state["weight"]
        model: torch.nn.Module = torch.nn.Linear(int(weight.shape[1]), len(attributes))
    elif architecture == "mlp":
        first_weight = state["0.weight"]
        hidden_dim = int(first_weight.shape[0])
        model = torch.nn.Sequential(
            torch.nn.Linear(int(first_weight.shape[1]), hidden_dim),
            torch.nn.GELU(),
            torch.nn.Dropout(0.15),
            torch.nn.Linear(hidden_dim, len(attributes)),
        )
    else:
        raise ValueError(f"unsupported fine attribute architecture: {architecture}")
    model.load_state_dict(state)
    model = model.to(device).eval()
    checkpoint = raw["checkpoint"]
    revision = raw["revision"]
    if not isinstance(checkpoint, str) or not isinstance(revision, str):
        raise ValueError("fine attribute CLIP identity is invalid")
    return FineHead(model, attributes, thresholds, checkpoint, revision)


def discover_fine_head_paths(model_directory: str | Path) -> tuple[Path | None, Path | None]:
    """Find the already-produced local PETA/PA100k heads without copying weights."""

    model_root = Path(model_directory).expanduser()
    experiments_root = model_root.parent / "experiments" / "models"
    roots = (model_root, experiments_root, Path.cwd() / "experiments" / "models")
    peta_names = (
        "clip_vitl14_peta_finetuned_head_20260731.pt",
        "clip_vitl14_peta_finetuned_head.pt",
    )
    pa_names = (
        "clip_vitl14_pa100k_finetuned_head_20k_20260731.pt",
        "clip_vitl14_pa100k_finetuned_head_20260731.pt",
        "clip_vitl14_pa100k_finetuned_head.pt",
    )

    def first_existing(names: tuple[str, ...]) -> Path | None:
        for root in roots:
            for name in names:
                candidate = root / name
                if candidate.is_file():
                    return candidate
        return None

    return first_existing(peta_names), first_existing(pa_names)


class FineAttributeRuntime:
    """Optional CLIP ViT-L/14 PETA + PA100k heads sharing the cached CLIP model."""

    def __init__(self, peta_path: Path, pa100k_path: Path, bundle: Any, device: str) -> None:
        self._device = torch.device(device)
        self._bundle = bundle
        self._peta = _load_head(peta_path, self._device)
        self._pa100k = _load_head(pa100k_path, self._device)
        if (self._peta.checkpoint, self._peta.revision) != (
            self._pa100k.checkpoint,
            self._pa100k.revision,
        ):
            raise ValueError("PETA and PA100k heads must share a CLIP checkpoint and revision")

    @staticmethod
    def _head_images(image: Image.Image) -> Image.Image:
        width, height = image.size
        return image.crop(
            (
                round(width * 0.10),
                0,
                max(round(width * 0.90), 1),
                max(round(height * 0.45), 1),
            )
        )

    def _feature_batch(self, frames: Sequence[TrackFrame]) -> torch.Tensor:
        full_images: list[Image.Image] = []
        head_images: list[Image.Image] = []
        for frame in frames:
            with Image.open(frame.crop_path) as source:
                full = source.convert("RGB")
            full_images.append(full)
            head_images.append(self._head_images(full))
        region_features: list[torch.Tensor] = []
        try:
            for images in (full_images, head_images):
                inputs = self._bundle.processor(images=images, return_tensors="pt")
                pixel_values = inputs["pixel_values"].to(
                    self._device,
                    dtype=self._bundle.model.dtype,
                )
                with torch.inference_mode():
                    features = pooled_clip_features(
                        self._bundle.model.get_image_features(pixel_values=pixel_values)
                    )
                    region_features.append(torch.nn.functional.normalize(features, dim=-1).float())
            return torch.cat(region_features, dim=1)
        finally:
            for image in (*full_images, *head_images):
                image.close()

    @staticmethod
    def _attribute_key(name: str) -> str | None:
        normalized = re_normalize(name)
        if "glass" in normalized or "spectacle" in normalized:
            return "glasses"
        if "hat" in normalized or "headwear" in normalized or "cap" in normalized:
            return "hat"
        if "hair" in normalized:
            return "hair"
        if "sleeve" in normalized or "upper" in normalized or "shirt" in normalized:
            return "upper_style"
        return None

    @staticmethod
    def _track_quality(frame: TrackFrame) -> float:
        try:
            with Image.open(frame.crop_path) as image:
                width, height = image.size
        except OSError:
            return 0.0
        return max(0.0, min(1.0, width / 96.0) * min(1.0, height / 256.0))

    def score(self, frames: Sequence[TrackFrame]) -> dict[int, dict[str, float]]:
        if not frames:
            return {}
        features = torch.cat(
            [self._feature_batch(frames[start : start + 32]) for start in range(0, len(frames), 32)]
        )
        probabilities: list[tuple[FineHead, torch.Tensor]] = []
        with torch.inference_mode():
            for head in (self._peta, self._pa100k):
                probabilities.append((head, torch.sigmoid(head.model(features)).cpu()))

        grouped: dict[int, list[int]] = defaultdict(list)
        for index, frame in enumerate(frames):
            grouped[frame.track_id].append(index)
        output: dict[int, dict[str, float]] = {}
        for track_id, indices in grouped.items():
            values: dict[str, list[float]] = defaultdict(list)
            for head, tensor in probabilities:
                for attribute_index, name in enumerate(head.attributes):
                    key = self._attribute_key(name)
                    if key is None:
                        continue
                    values[key].extend(float(tensor[index, attribute_index]) for index in indices)
            output[track_id] = {
                key: max(0.0, min(1.0, sum(items) / len(items)))
                for key, items in values.items()
                if items
            }
        return output


@dataclass(frozen=True, slots=True)
class SoliderParHead:
    model: torch.nn.Module
    attributes: tuple[str, ...]
    checkpoint: str


def discover_solider_par_head_path(
    model_directory: str | Path,
    explicit_path: Path | None = None,
) -> Path | None:
    """Resolve a local SOLIDER-PAR head without treating remote manifests as weights."""

    if explicit_path is not None:
        return explicit_path.expanduser() if explicit_path.is_file() else None
    model_root = Path(model_directory).expanduser()
    roots = (
        model_root,
        model_root.parent / "experiments" / "models",
        Path.cwd() / "experiments" / "models",
    )
    names = (
        "solider_sonnet_head_pilot.pt",
        "solider-pa100k-head.pt",
        "solider_pa100k_head.pt",
        "solider_par_head.pt",
    )
    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate
    return None


def _load_solider_par_head(path: Path, device: torch.device) -> SoliderParHead:
    payload = torch.load(path, map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise ValueError("SOLIDER PAR checkpoint must contain a mapping")
    raw = cast(dict[str, object], payload)
    state_value = raw.get("state_dict")
    attributes_value = raw.get("attributes")
    if not isinstance(state_value, Mapping) or not isinstance(attributes_value, (list, tuple)):
        raise ValueError("SOLIDER PAR checkpoint schema is invalid")
    attribute_items = cast(list[object] | tuple[object, ...], attributes_value)
    attributes = tuple(value for value in attribute_items if isinstance(value, str))
    if not attributes or len(attributes) != len(attribute_items):
        raise ValueError("SOLIDER PAR attributes are invalid")
    state_items = cast(Mapping[str, object], state_value)
    if not all(isinstance(value, torch.Tensor) for value in state_items.values()):
        raise ValueError("SOLIDER PAR state values are invalid")
    state = cast(dict[str, torch.Tensor], dict(state_items))
    weight = state.get("weight")
    if not isinstance(weight, torch.Tensor) or weight.ndim != 2:
        raise ValueError("SOLIDER PAR checkpoint must contain a linear weight")
    head = torch.nn.Linear(int(weight.shape[1]), len(attributes))
    head.load_state_dict(state)
    return SoliderParHead(head.to(device).eval(), attributes, str(path))


class SoliderParRuntime:
    """SOLIDER Swin-B feature + PA-100K/Sonnet auxiliary attribute head."""

    def __init__(self, checkpoint: Path, device: str) -> None:
        self._device = torch.device(device)
        self._head = _load_solider_par_head(checkpoint, self._device)

    def score(self, frames: Sequence[TrackFrame], encoder: Any) -> dict[int, dict[str, float]]:
        if not frames:
            return {}
        features: list[torch.Tensor] = []
        for start in range(0, len(frames), 32):
            tensors: list[torch.Tensor] = []
            for frame in frames[start : start + 32]:
                with Image.open(frame.crop_path) as source:
                    converted = source.convert("RGB")
                    try:
                        tensors.append(encoder.processor(converted))
                    finally:
                        converted.close()
            batch = torch.stack(tensors).to(self._device)
            with torch.inference_mode():
                output = encoder.model(batch)[0]
                if output.ndim == 4:
                    output = torch.nn.functional.adaptive_avg_pool2d(output, 1).flatten(1)
                if output.ndim != 2:
                    raise ValueError("SOLIDER PAR backbone output must be rank 2 or 4")
                features.append(output.float())
        probabilities = torch.sigmoid(self._head.model(torch.cat(features, dim=0))).detach().cpu()
        grouped: dict[int, list[int]] = defaultdict(list)
        for index, frame in enumerate(frames):
            grouped.setdefault(frame.track_id, []).append(index)
        output_by_track: dict[int, dict[str, float]] = {}
        for track_id, indices in grouped.items():
            values: dict[str, list[float]] = defaultdict(list)
            for attribute_index, attribute_name in enumerate(self._head.attributes):
                key = self._attribute_key(attribute_name)
                if key is None:
                    continue
                values[key].extend(
                    float(probabilities[index, attribute_index]) for index in indices
                )
            output_by_track[track_id] = {
                key: max(0.0, min(1.0, sum(items) / len(items)))
                for key, items in values.items()
                if items
            }
        return output_by_track

    @staticmethod
    def _attribute_key(name: str) -> str | None:
        normalized = re_normalize(name)
        if "glass" in normalized or "spectacle" in normalized:
            return "glasses"
        if "hair" in normalized:
            return "hair"
        if any(token in normalized for token in ("sleeve", "upper", "shirt", "tshirt")):
            return "upper_style"
        return None


def re_normalize(value: str) -> str:
    return "".join(character for character in value.lower() if character.isalnum())

