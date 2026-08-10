from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from run_solider_pa100k_parquet import ATTRIBUTES
from run_solider_sonnet_head_pilot import map_attributes
from torch import Tensor, nn

MEAN = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
STD = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
GROUP_PATTERN = re.compile(r"^(ped_(\d+))_img(\d+)\.png$")


class ExperimentRuntimeError(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_labels(record: dict[str, Any]) -> tuple[Tensor, Tensor]:
    labels, mask = map_attributes(record)
    accessory = str(record.get("accessory", "")).lower()
    for terms, attribute in (
        (("backpack", "rucksack"), "Backpack"),
        (("shoulder bag", "crossbody", "sling bag"), "ShoulderBag"),
        (("handbag", "hand bag", "purse"), "HandBag"),
    ):
        if any(term in accessory for term in terms):
            index = ATTRIBUTES.index(attribute)
            labels[index] = 1.0
            mask[index] = 1.0
    return labels, mask


def image_tensor(path: Path) -> Tensor:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((128, 256), Image.Resampling.BICUBIC)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return (torch.from_numpy(array).permute(2, 0, 1) - MEAN) / STD


def load_simuletic(root: Path, metadata_path: Path) -> tuple[dict[str, Any], ...]:
    rows: list[dict[str, Any]] = []
    for line in metadata_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict) or not isinstance(raw.get("image"), str):
            raise ExperimentRuntimeError("invalid Simuletic metadata row")
        match = GROUP_PATTERN.match(raw["image"])
        if match is None:
            continue
        image_path = (root / raw["image"]).resolve()
        if not image_path.is_file():
            continue
        attributes = raw.get("attributes")
        if not isinstance(attributes, dict):
            raise ExperimentRuntimeError(f"missing attributes: {raw['image']}")
        labels, mask = record_labels({str(k): v for k, v in attributes.items()})
        rows.append({
            "image": image_path,
            "group": match.group(1),
            "identity": int(match.group(2)),
            "frame": int(match.group(3)),
            "labels": labels,
            "mask": mask,
        })
    if len(rows) < 30:
        raise ExperimentRuntimeError(f"too few available Simuletic rows: {len(rows)}")
    return tuple(rows)


def group_split(rows: tuple[dict[str, Any], ...]) -> tuple[set[int], set[int], set[int]]:
    identities = sorted({int(row["identity"]) for row in rows})
    if len(identities) < 3:
        raise ExperimentRuntimeError("at least three Simuletic identity groups are required")
    train_end = max(1, int(len(identities) * 0.6))
    val_end = min(len(identities) - 1, max(train_end + 1, int(len(identities) * 0.8)))
    return set(identities[:train_end]), set(identities[train_end:val_end]), set(identities[val_end:])


def feature_rows(
    backbone: nn.Module,
    rows: tuple[dict[str, Any], ...],
    device: torch.device,
    batch_size: int,
) -> Tensor:
    chunks: list[Tensor] = []
    backbone.eval()
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            batch_rows = rows[start : start + batch_size]
            paths = [row["image"] for row in batch_rows]
            if not all(isinstance(path, Path) for path in paths):
                raise ExperimentRuntimeError("invalid image path")
            images = torch.stack([image_tensor(path) for path in paths]).to(device)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = backbone(images)
            chunks.append(nn.functional.adaptive_avg_pool2d(output, 1).flatten(1).float().cpu())
    return torch.cat(chunks, dim=0)


def masked_metrics(logits: Tensor, labels: Tensor, mask: Tensor) -> dict[str, float]:
    predicted = logits.sigmoid().ge(0.5)
    actual = labels.ge(0.5)
    valid = mask.ge(0.5)
    if not bool(valid.any()):
        raise ExperimentRuntimeError("no valid labels")
    fields = [
        float((predicted[valid[:, index], index] == actual[valid[:, index], index]).float().mean())
        for index in range(labels.shape[1])
        if bool(valid[:, index].any())
    ]
    return {
        "masked_attribute_accuracy": float(((predicted == actual) & valid).sum() / valid.sum()),
        "masked_field_macro_accuracy": float(sum(fields) / len(fields)),
        "valid_attribute_count": float(valid.sum()),
    }


def group_metrics(
    logits: Tensor, rows: tuple[dict[str, Any], ...], indices: tuple[int, ...]
) -> dict[str, float]:
    by_group: dict[str, list[int]] = {}
    for index in indices:
        by_group.setdefault(str(rows[index]["group"]), []).append(index)
    exact = 0
    scores: list[float] = []
    for group_indices in by_group.values():
        aggregate = logits[group_indices].mean(dim=0, keepdim=True)
        target = torch.stack([rows[group_indices[0]]["labels"]])
        mask = torch.stack([rows[group_indices[0]]["mask"]])
        scores.append(masked_metrics(aggregate, target, mask)["masked_attribute_accuracy"])
        prediction = aggregate.sigmoid().ge(0.5)
        actual = target.ge(0.5)
        valid = mask.ge(0.5)
        if bool(((prediction == actual) | ~valid).all()):
            exact += 1
    return {
        "groups": float(len(by_group)),
        "group_masked_attribute_accuracy": float(sum(scores) / len(scores)),
        "group_exact_rate": float(exact / max(1, len(by_group))),
    }


def load_sonnet(
    result_path: Path, image_root: Path, backbone: nn.Module, device: torch.device
) -> tuple[Tensor, Tensor, Tensor, Tensor] | None:
    if not result_path.is_file():
        return None
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    samples = payload.get("samples") if isinstance(payload, dict) else None
    if not isinstance(samples, list) or not samples:
        return None
    rows: list[dict[str, Any]] = []
    for sample in samples:
        if not isinstance(sample, dict) or not isinstance(sample.get("image"), str):
            continue
        image_path = (image_root / sample["image"]).resolve()
        prediction = sample.get("prediction")
        if not image_path.is_file() or not isinstance(prediction, dict):
            continue
        labels, mask = map_attributes(prediction)
        confidence = prediction.get("teacher_confidence", 1.0)
        weight = float(confidence) if isinstance(confidence, (int, float)) else 1.0
        rows.append({"image": image_path, "labels": labels, "mask": mask, "weight": max(0.5, min(weight, 1.0))})
    if not rows:
        return None
    features = feature_rows(backbone, tuple(rows), device, 32)
    return (
        features,
        torch.stack([row["labels"] for row in rows]),
        torch.stack([row["mask"] for row in rows]),
        torch.tensor([row["weight"] for row in rows], dtype=torch.float32),
    )

