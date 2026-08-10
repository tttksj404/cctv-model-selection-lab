# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2.0",
#   "pillow>=10",
#   "pyarrow>=18",
#   "torch==2.11.0+cu128",
# ]
# ///

from __future__ import annotations

import copy
import hashlib
import json
import platform
import random
import re
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from run_solider_pa100k_parquet import (
    ATTRIBUTES,
    _extract_split,
    _load_backbone,
    _metrics,
    _official_bce_loss,
)

MEAN = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
STD = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
GROUP_PATTERN = re.compile(r"^(ped_[^_]+)_img\d+\.png$")


class ExperimentRuntimeError(RuntimeError):
    pass


class ExperimentOutputError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def as_dict(value: object, name: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ExperimentRuntimeError(f"{name} must be an object")
    return {str(key): item for key, item in value.items()}


def text(value: object) -> str:
    return value.lower() if isinstance(value, str) else ""


def contains(value: object, *terms: str) -> bool:
    value_text = text(value)
    return any(term in value_text for term in terms)


def set_label(labels: dict[str, float], mask: dict[str, float], name: str, value: float) -> None:
    labels[name] = value
    mask[name] = 1.0


def map_attributes(record: dict[str, object]) -> tuple[Tensor, Tensor]:
    labels = {name: 0.0 for name in ATTRIBUTES}
    mask = {name: 0.0 for name in ATTRIBUTES}
    gender = record.get("gender")
    if contains(gender, "female", "woman", "girl"):
        set_label(labels, mask, "Female", 1.0)
    elif contains(gender, "male", "man", "boy"):
        set_label(labels, mask, "Female", 0.0)
    age = record.get("age_group", record.get("age"))
    if contains(age, "senior", "elderly", "over60"):
        for name, value in (("AgeOver60", 1.0), ("Age18-60", 0.0), ("AgeLess18", 0.0)):
            set_label(labels, mask, name, value)
    elif contains(age, "young", "adult", "18", "middle"):
        for name, value in (("AgeOver60", 0.0), ("Age18-60", 1.0), ("AgeLess18", 0.0)):
            set_label(labels, mask, name, value)
    elif contains(age, "child", "under18"):
        for name, value in (("AgeOver60", 0.0), ("Age18-60", 0.0), ("AgeLess18", 1.0)):
            set_label(labels, mask, name, value)
    viewpoint = record.get("viewpoint", record.get("angle"))
    if contains(viewpoint, "front"):
        for name, value in (("Front", 1.0), ("Side", 0.0), ("Back", 0.0)):
            set_label(labels, mask, name, value)
    elif contains(viewpoint, "side", "profile"):
        for name, value in (("Front", 0.0), ("Side", 1.0), ("Back", 0.0)):
            set_label(labels, mask, name, value)
    elif contains(viewpoint, "back", "rear"):
        for name, value in (("Front", 0.0), ("Side", 0.0), ("Back", 1.0)):
            set_label(labels, mask, name, value)
    accessory = record.get("accessory")
    if contains(accessory, "sunglasses", "glasses", "eyeglasses"):
        set_label(labels, mask, "Glasses", 1.0)
    if contains(accessory, "hat", "cap") and not contains(accessory, "held", "holding", "hand"):
        set_label(labels, mask, "Hat", 1.0)
    if contains(accessory, "phone", "smartphone", "mobile"):
        set_label(labels, mask, "HoldObjectsInFront", 1.0)
    top_type = record.get("top_type")
    if contains(top_type, "short-sleeve", "short sleeve", "t-shirt", "tee"):
        set_label(labels, mask, "ShortSleeve", 1.0)
        set_label(labels, mask, "LongSleeve", 0.0)
    elif contains(top_type, "long-sleeve", "long sleeve", "sweater", "jacket", "coat"):
        set_label(labels, mask, "ShortSleeve", 0.0)
        set_label(labels, mask, "LongSleeve", 1.0)
    bottom_type = record.get("bottom_type")
    if contains(bottom_type, "trouser", "pants", "leggings", "sweatpants", "cargo"):
        values = (("Trousers", 1.0), ("Shorts", 0.0), ("Skirt&Dress", 0.0))
    elif contains(bottom_type, "shorts"):
        values = (("Trousers", 0.0), ("Shorts", 1.0), ("Skirt&Dress", 0.0))
    elif contains(bottom_type, "skirt", "dress"):
        values = (("Trousers", 0.0), ("Shorts", 0.0), ("Skirt&Dress", 1.0))
    else:
        values = ()
    for name, value in values:
        set_label(labels, mask, name, value)
    return (
        torch.tensor([labels[name] for name in ATTRIBUTES], dtype=torch.float32),
        torch.tensor([mask[name] for name in ATTRIBUTES], dtype=torch.float32),
    )


def load_samples(result_path: Path, image_root: Path) -> tuple[dict[str, object], ...]:
    payload = as_dict(json.loads(result_path.read_text(encoding="utf-8")), "sonnet result")
    raw_samples = payload.get("samples")
    if not isinstance(raw_samples, list) or not raw_samples:
        raise ExperimentRuntimeError("sonnet result contains no samples")
    image_root = image_root.resolve()
    samples: list[dict[str, object]] = []
    for raw in raw_samples:
        item = as_dict(raw, "sample")
        image_name = item.get("image")
        if not isinstance(image_name, str):
            raise ExperimentRuntimeError("sample image must be a string")
        image_path = (image_root / image_name).resolve()
        if image_root not in image_path.parents or not image_path.is_file():
            raise ExperimentRuntimeError(f"sample image escapes image root: {image_name}")
        prediction = as_dict(item.get("prediction"), "prediction")
        target = as_dict(item.get("target"), "target")
        match = GROUP_PATTERN.match(image_name)
        if match is None:
            raise ExperimentRuntimeError(f"image does not contain a track group: {image_name}")
        prediction_labels, prediction_mask = map_attributes(prediction)
        target_labels, target_mask = map_attributes(target)
        confidence = prediction.get("teacher_confidence", 1.0)
        weight = float(confidence) if isinstance(confidence, (int, float)) else 1.0
        samples.append(
            {
                "image": image_path,
                "group": match.group(1),
                "prediction_labels": prediction_labels,
                "prediction_mask": prediction_mask,
                "target_labels": target_labels,
                "target_mask": target_mask,
                "teacher_weight": max(0.5, min(weight, 1.0)),
            }
        )
    return tuple(samples)


def image_tensor(path: Path) -> Tensor:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((128, 256), Image.Resampling.BICUBIC)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return (torch.from_numpy(array).permute(2, 0, 1) - MEAN) / STD


def image_features(
    backbone: nn.Module, samples: tuple[dict[str, object], ...], device: torch.device
) -> Tensor:
    chunks: list[Tensor] = []
    backbone.eval()
    with torch.inference_mode():
        for start in range(0, len(samples), 8):
            paths = [item["image"] for item in samples[start : start + 8]]
            if not all(isinstance(path, Path) for path in paths):
                raise ExperimentRuntimeError("sample image path is invalid")
            batch = torch.stack([image_tensor(path) for path in paths]).to(device)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = backbone(batch)
            chunks.append(nn.functional.adaptive_avg_pool2d(output, 1).flatten(1).float().cpu())
    return torch.cat(chunks, dim=0)


def train_pa_head(features: Tensor, labels: Tensor, epochs: int, device: torch.device) -> nn.Linear:
    head = nn.Linear(features.shape[1], labels.shape[1]).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.001, weight_decay=0.0001)
    ratio = labels.mean(dim=0)
    for _ in range(epochs):
        order = torch.randperm(features.shape[0])
        for start in range(0, len(order), 512):
            indices = order[start : start + 512]
            loss = _official_bce_loss(
                head(features[indices].to(device)), labels[indices].to(device), ratio
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def train_combined_head(
    initial: nn.Linear,
    pa_features: Tensor,
    pa_labels: Tensor,
    sonnet_features: Tensor,
    sonnet_labels: Tensor,
    sonnet_mask: Tensor,
    sonnet_weights: Tensor,
    epochs: int,
    device: torch.device,
    sonnet_weight: float,
) -> nn.Linear:
    head = copy.deepcopy(initial).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.0002, weight_decay=0.0001)
    ratio = pa_labels.mean(dim=0)
    for _ in range(epochs):
        order = torch.randperm(pa_features.shape[0])
        for start in range(0, len(order), 512):
            indices = order[start : start + 512]
            pa_loss = _official_bce_loss(
                head(pa_features[indices].to(device)), pa_labels[indices].to(device), ratio
            )
            logits = head(sonnet_features.to(device))
            values = F.binary_cross_entropy_with_logits(
                logits, sonnet_labels.to(device), reduction="none"
            )
            weighted_mask = sonnet_mask.to(device) * sonnet_weights.view(-1, 1).to(device)
            teacher_loss = (values * weighted_mask).sum() / weighted_mask.sum().clamp_min(1.0)
            loss = pa_loss + sonnet_weight * teacher_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def predict(head: nn.Module, features: Tensor, device: torch.device) -> Tensor:
    with torch.inference_mode():
        return head(features.to(device)).float().cpu()


def masked_metrics(logits: Tensor, labels: Tensor, mask: Tensor) -> dict[str, float]:
    predicted = logits.sigmoid().ge(0.5)
    actual = labels.ge(0.5)
    valid = mask.ge(0.5)
    if not bool(valid.any()):
        raise ExperimentRuntimeError("no valid mapped attributes")
    field_scores = [
        float((predicted[valid[:, index], index] == actual[valid[:, index], index]).float().mean())
        for index in range(labels.shape[1])
        if bool(valid[:, index].any())
    ]
    balanced_scores: list[float] = []
    for index in range(labels.shape[1]):
        field_valid = valid[:, index]
        field_actual = actual[field_valid, index]
        field_predicted = predicted[field_valid, index]
        positives = field_actual
        negatives = ~field_actual
        if bool(positives.any()) and bool(negatives.any()):
            true_positive_rate = (field_predicted[positives] == positives[positives]).float().mean()
            true_negative_rate = (field_predicted[negatives] == negatives[negatives]).float().mean()
            balanced_scores.append(float(((true_positive_rate + true_negative_rate) / 2).item()))
    return {
        "masked_attribute_accuracy": float(
            ((predicted == actual) & valid).sum().float().div(valid.sum()).item()
        ),
        "masked_field_macro_accuracy": sum(field_scores) / len(field_scores),
        "masked_mA": sum(balanced_scores) / len(balanced_scores) if balanced_scores else -1.0,
        "balanced_field_count": float(len(balanced_scores)),
        "valid_attribute_count": float(valid.sum().item()),
    }


def load_head_checkpoint(
    checkpoint_path: Path, feature_count: int, device: torch.device
) -> nn.Linear:
    payload = torch.load(checkpoint_path.resolve(), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict):
        raise ExperimentRuntimeError("base head checkpoint must contain an object")
    state_dict = payload.get("state_dict")
    attributes = payload.get("attributes")
    if not isinstance(state_dict, dict) or not isinstance(attributes, list):
        raise ExperimentRuntimeError("base head checkpoint has an invalid schema")
    if tuple(str(attribute) for attribute in attributes) != ATTRIBUTES:
        raise ExperimentRuntimeError("base head checkpoint attributes do not match PA-100K")
    head = nn.Linear(feature_count, len(ATTRIBUTES))
    try:
        head.load_state_dict(state_dict)
    except RuntimeError as error:
        raise ExperimentRuntimeError(
            "base head checkpoint shape does not match backbone"
        ) from error
    return head.to(device).eval()


def group_cv(
    baseline: nn.Linear,
    pa_features: Tensor,
    pa_labels: Tensor,
    features: Tensor,
    predictions: Tensor,
    prediction_masks: Tensor,
    targets: Tensor,
    target_masks: Tensor,
    weights: Tensor,
    groups: tuple[str, ...],
    sample_groups: tuple[str, ...],
    epochs: int,
    device: torch.device,
    sonnet_weight: float,
) -> dict[str, object]:
    baseline_logits = predict(baseline, features, device)
    folds: list[dict[str, object]] = []
    for heldout in groups:
        train_indices = tuple(
            index for index, group in enumerate(sample_groups) if group != heldout
        )
        test_indices = tuple(index for index, group in enumerate(sample_groups) if group == heldout)
        train_tensor = torch.tensor(train_indices)
        test_tensor = torch.tensor(test_indices)
        adapted = train_combined_head(
            baseline,
            pa_features,
            pa_labels,
            features[train_tensor],
            predictions[train_tensor],
            prediction_masks[train_tensor],
            weights[train_tensor],
            epochs,
            device,
            sonnet_weight,
        )
        baseline_score = masked_metrics(
            baseline_logits[test_tensor], targets[test_tensor], target_masks[test_tensor]
        )
        adapted_score = masked_metrics(
            predict(adapted, features[test_tensor], device),
            targets[test_tensor],
            target_masks[test_tensor],
        )
        folds.append(
            {
                "heldout_group": heldout,
                "train_groups": sorted({sample_groups[index] for index in train_indices}),
                "test_count": len(test_indices),
                "baseline": baseline_score,
                "solider_plus_sonnet": adapted_score,
                "delta_masked_attribute_accuracy": adapted_score["masked_attribute_accuracy"]
                - baseline_score["masked_attribute_accuracy"],
            }
        )
    baseline_values = [fold["baseline"]["masked_attribute_accuracy"] for fold in folds]
    combined_values = [fold["solider_plus_sonnet"]["masked_attribute_accuracy"] for fold in folds]
    baseline_mean = sum(baseline_values) / len(baseline_values)
    combined_mean = sum(combined_values) / len(combined_values)
    return {
        "folds": folds,
        "baseline_mean_masked_attribute_accuracy": baseline_mean,
        "combined_mean_masked_attribute_accuracy": combined_mean,
        "mean_delta_masked_attribute_accuracy": combined_mean - baseline_mean,
    }


def run(
    output: Path = Path("experiments/results/solider_sonnet_head_pilot.json"),
    sonnet_result: Path = Path("experiments/results/sonnet_cli_pilot.json"),
    image_root: Path = Path("experiments/data/cctv_proxy/person_only/simuletic"),
    data_root: Path = Path("experiments/data/pa100k_full"),
    checkpoint: Path = Path("experiments/models/solider_swin_base.pth"),
    pa_train_rows: int = 2_000,
    pa_val_rows: int = 500,
    pa_test_rows: int = 500,
    extract_batch_size: int = 32,
    pa_epochs: int = 1,
    sonnet_epochs: int = 12,
    sonnet_weight: float = 0.10,
    base_head_checkpoint: Path | None = None,
    seed: int = 20260723,
) -> None:
    if not torch.cuda.is_available():
        raise ExperimentRuntimeError("CUDA is required")
    if not 0 < sonnet_weight <= 1:
        raise ValueError("sonnet_weight must be in (0, 1]")
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    device = torch.device("cuda")
    samples = load_samples(sonnet_result.resolve(), image_root)
    groups = tuple(sorted({str(item["group"]) for item in samples}))
    if len(groups) < 3:
        raise ExperimentRuntimeError("at least three track groups are required")
    backbone = _load_backbone(checkpoint.resolve()).to(device)
    backbone.eval()
    train_features, train_labels = _extract_split(
        data_root / "train.parquet", backbone, device, extract_batch_size, pa_train_rows
    )
    val_features, val_labels = _extract_split(
        data_root / "val.parquet", backbone, device, extract_batch_size, pa_val_rows
    )
    test_features, test_labels = _extract_split(
        data_root / "test.parquet", backbone, device, extract_batch_size, pa_test_rows
    )
    sonnet_features = image_features(backbone, samples, device)
    del backbone
    torch.cuda.empty_cache()
    predictions = torch.stack([item["prediction_labels"] for item in samples])
    prediction_masks = torch.stack([item["prediction_mask"] for item in samples])
    targets = torch.stack([item["target_labels"] for item in samples])
    target_masks = torch.stack([item["target_mask"] for item in samples])
    weights = torch.tensor([float(item["teacher_weight"]) for item in samples])
    if base_head_checkpoint is None:
        baseline = train_pa_head(train_features, train_labels, pa_epochs, device)
        baseline_initialization = "new_pa_head"
    else:
        baseline = load_head_checkpoint(
            base_head_checkpoint.resolve(), train_features.shape[1], device
        )
        baseline_initialization = "saved_pa_head_checkpoint"
    baseline_proxy = masked_metrics(
        predict(baseline, sonnet_features, device), targets, target_masks
    )
    combined = train_combined_head(
        baseline,
        train_features,
        train_labels,
        sonnet_features,
        predictions,
        prediction_masks,
        weights,
        sonnet_epochs,
        device,
        sonnet_weight,
    )
    combined_proxy = masked_metrics(
        predict(combined, sonnet_features, device), targets, target_masks
    )
    combined_val_logits = predict(combined, val_features, device)
    combined_test_logits = predict(combined, test_features, device)
    combined_pa_metrics = {
        "val": {
            **masked_metrics(combined_val_logits, val_labels, torch.ones_like(val_labels)),
            "official": _metrics(combined_val_logits, val_labels),
        },
        "test": {
            **masked_metrics(combined_test_logits, test_labels, torch.ones_like(test_labels)),
            "official": _metrics(combined_test_logits, test_labels),
        },
    }
    result_group_cv = group_cv(
        baseline,
        train_features,
        train_labels,
        sonnet_features,
        predictions,
        prediction_masks,
        targets,
        target_masks,
        weights,
        groups,
        tuple(str(item["group"]) for item in samples),
        sonnet_epochs,
        device,
        sonnet_weight,
    )
    baseline_val_logits = predict(baseline, val_features, device)
    baseline_test_logits = predict(baseline, test_features, device)
    pa_metrics = {
        "val": {
            **masked_metrics(baseline_val_logits, val_labels, torch.ones_like(val_labels)),
            "official": _metrics(baseline_val_logits, val_labels),
        },
        "test": {
            **masked_metrics(baseline_test_logits, test_labels, torch.ones_like(test_labels)),
            "official": _metrics(baseline_test_logits, test_labels),
        },
    }
    output = output.resolve()
    workspace = Path.cwd().resolve()
    if workspace not in output.parents:
        raise ExperimentOutputError("output must be inside workspace")
    head_path = workspace / "experiments/models/solider_sonnet_head_pilot.pt"
    baseline_path = workspace / "experiments/models/solider_sonnet_baseline_head.pt"
    if output in {head_path, baseline_path}:
        raise ExperimentOutputError("output must not overwrite a checkpoint")
    base_head_checkpoint_sha256 = None
    if base_head_checkpoint is not None:
        base_head_path = base_head_checkpoint.resolve()
        if base_head_path in {output, head_path, baseline_path}:
            raise ExperimentOutputError("base head checkpoint must not overwrite an output")
        base_head_checkpoint_sha256 = sha256_file(base_head_path)
    torch.save(
        {
            "state_dict": baseline.state_dict(),
            "attributes": list(ATTRIBUTES),
            "source": baseline_initialization,
            "sonnet_weight": sonnet_weight,
        },
        baseline_path,
    )
    torch.save(
        {
            "state_dict": combined.state_dict(),
            "attributes": list(ATTRIBUTES),
            "sonnet_weight": sonnet_weight,
        },
        head_path,
    )
    artifact = {
        "status": "measured",
        "model": "SOLIDER Swin-B frozen backbone plus PA-100K 26-attribute head",
        "method": "PA-100K head training plus masked response-level Sonnet auxiliary loss",
        "dataset": "PA-100K official parquet plus synthetic CCTV person-crop proxy",
        "rows": {"pa_train": pa_train_rows, "pa_val": pa_val_rows, "pa_test": pa_test_rows},
        "cctv_proxy_samples": len(samples),
        "cctv_proxy_groups": list(groups),
        "split": "group-held-out by synthetic person track; no reviewed project identity labels",
        "device": torch.cuda.get_device_name(0),
        "runtime": {"python": platform.python_version(), "torch": torch.__version__},
        "sonnet_teacher": "claude-sonnet-5 via authenticated Claude Code CLI",
        "sonnet_label_type": "response-level labels mapped to PA-100K ontology; not logit KD",
        "sonnet_weight": sonnet_weight,
        "pa_epochs": pa_epochs,
        "sonnet_epochs": sonnet_epochs,
        "baseline_initialization": baseline_initialization,
        "baseline_head_checkpoint": str(baseline_path),
        "baseline_head_checkpoint_sha256": sha256_file(baseline_path),
        "baseline_pa100k": pa_metrics,
        "combined_pa100k": combined_pa_metrics,
        "baseline_proxy_all_samples": baseline_proxy,
        "combined_proxy_all_samples": combined_proxy,
        "group_heldout": result_group_cv,
        "checkpoint": str(head_path),
        "checkpoint_sha256": sha256_file(head_path),
        "provenance": {
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "solider_checkpoint_sha256": sha256_file(checkpoint.resolve()),
            "sonnet_result_sha256": sha256_file(sonnet_result.resolve()),
            "base_head_checkpoint_sha256": (
                base_head_checkpoint_sha256
            ),
        },
        "gate": {
            "target": 0.85,
            "passed": False,
            "reason": (
                "Synthetic proxy and response-level labels cannot establish CCTV "
                "identity/track-heldout accuracy."
            ),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "baseline_proxy": baseline_proxy,
                "combined_proxy": combined_proxy,
                "group_heldout": result_group_cv,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    import typer

    typer.run(run)

