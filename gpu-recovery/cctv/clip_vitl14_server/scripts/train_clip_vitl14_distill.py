# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2.0",
#   "pillow>=10",
#   "pyarrow>=18",
#   "torch==2.11.0+cu128",
#   "transformers==5.14.1",
#   "typer>=0.15,<1",
# ]
# ///
# How to run:
# run: uv run scripts/train_clip_vitl14_distill.py --output results.json

from __future__ import annotations

import hashlib
import io
import json
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

import pyarrow.parquet as parquet
import torch
import typer
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional
from transformers import CLIPModel, CLIPProcessor

ATTRIBUTES = (
    "Female", "AgeOver60", "Age18-60", "AgeLess18", "Front", "Side", "Back",
    "Hat", "Glasses", "HandBag", "ShoulderBag", "Backpack", "HoldObjectsInFront",
    "ShortSleeve", "LongSleeve", "UpperStride", "UpperLogo", "UpperPlaid", "UpperSplice",
    "LowerStripe", "LowerPattern", "LongCoat", "Trousers", "Shorts", "Skirt&Dress", "boots",
)
IMAGE_COLUMNS = ["image", *ATTRIBUTES]
DEFAULT_DATA_ROOT = Path("experiments/data/pa100k_full")
DEFAULT_CLIP = "openai/clip-vit-large-patch14"


@dataclass(frozen=True, slots=True)
class SplitTensors:
    features: Tensor
    labels: Tensor


class BinaryAttributeHead(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.linear = nn.Linear(input_dim, len(ATTRIBUTES))

    def forward(self, features: Tensor) -> Tensor:
        return self.linear(features)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _decode(raw: bytes) -> Image.Image:
    with Image.open(io.BytesIO(raw)) as image:
        return image.convert("RGB")


def _clip_features(model: CLIPModel, pixels: Tensor) -> Tensor:
    output = model.get_image_features(pixel_values=pixels)
    features = output.pooler_output
    return features / features.norm(dim=1, keepdim=True).clamp_min(1e-6)


def extract_clip_split(
    path: Path,
    model: CLIPModel,
    processor: CLIPProcessor,
    device: torch.device,
    batch_size: int,
    limit: int,
) -> SplitTensors:
    features: list[Tensor] = []
    labels: list[Tensor] = []
    seen = 0
    with torch.inference_mode():
        batches = parquet.ParquetFile(path).iter_batches(
            batch_size=batch_size, columns=IMAGE_COLUMNS
        )
        for batch in batches:
            rows = batch.to_pydict()
            count = min(len(rows["image"]), limit - seen)
            images = [_decode(rows["image"][index]["bytes"]) for index in range(count)]
            encoded = processor(images=images, return_tensors="pt")["pixel_values"].to(device)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                features.append(_clip_features(model, encoded).float().cpu())
            labels.append(torch.tensor(
                [[int(rows[name][index]) for name in ATTRIBUTES] for index in range(count)],
                dtype=torch.float32,
            ))
            seen += count
            if seen >= limit:
                break
    if not features:
        raise RuntimeError(f"no rows extracted from {path}")
    return SplitTensors(torch.cat(features), torch.cat(labels))


def _weighted_bce(logits: Tensor, labels: Tensor, positive_ratio: Tensor) -> Tensor:
    weights = ((1 - positive_ratio) / positive_ratio.clamp_min(1e-4)).to(logits.device)
    return functional.binary_cross_entropy_with_logits(logits, labels, pos_weight=weights)


def train_head(
    data: SplitTensors,
    teacher_logits: Tensor | None,
    device: torch.device,
    epochs: int,
    batch_size: int,
    distill_alpha: float,
    temperature: float,
) -> BinaryAttributeHead:
    head = BinaryAttributeHead(data.features.shape[1]).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=2e-3, weight_decay=1e-4)
    positive_ratio = data.labels.mean(dim=0)
    for _ in range(epochs):
        order = torch.randperm(data.features.shape[0])
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            logits = head(data.features[indices].to(device))
            hard_loss = _weighted_bce(logits, data.labels[indices].to(device), positive_ratio)
            loss = hard_loss
            if teacher_logits is not None and distill_alpha > 0:
                soft_target = (teacher_logits[indices].to(device) / temperature).sigmoid()
                soft_loss = functional.binary_cross_entropy_with_logits(
                    logits / temperature, soft_target
                ) * temperature**2
                loss = (1 - distill_alpha) * hard_loss + distill_alpha * soft_loss
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def choose_thresholds(logits: Tensor, labels: Tensor) -> Tensor:
    candidates = torch.arange(0.20, 0.81, 0.05)
    probabilities = logits.sigmoid()
    thresholds: list[float] = []
    for index in range(labels.shape[1]):
        best = (0.5, -1.0)
        for candidate in candidates:
            predicted = probabilities[:, index] >= candidate
            actual = labels[:, index] >= 0.5
            positive = actual.sum().clamp_min(1)
            negative = (~actual).sum().clamp_min(1)
            true_positive_rate = (predicted & actual).sum() / positive
            true_negative_rate = ((~predicted) & (~actual)).sum() / negative
            score = float(((true_positive_rate + true_negative_rate) / 2).item())
            if score > best[1] or (
                score == best[1] and abs(float(candidate) - 0.5) < abs(best[0] - 0.5)
            ):
                best = (float(candidate), score)
        thresholds.append(best[0])
    return torch.tensor(thresholds)


def metrics(logits: Tensor, labels: Tensor, thresholds: Tensor) -> dict[str, float]:
    predicted = logits.sigmoid().ge(thresholds.view(1, -1))
    actual = labels.ge(0.5)
    positive = actual
    negative = ~actual
    balanced = (
        ((predicted & positive).sum(0) / positive.sum(0).clamp_min(1))
        + ((~predicted & negative).sum(0) / negative.sum(0).clamp_min(1))
    ) / 2
    label_f1: list[float] = []
    for index in range(labels.shape[1]):
        tp = (predicted[:, index] & actual[:, index]).sum().float()
        fp = (predicted[:, index] & ~actual[:, index]).sum().float()
        fn = (~predicted[:, index] & actual[:, index]).sum().float()
        label_f1.append(float((2 * tp / (2 * tp + fp + fn).clamp_min(1)).item()))
    intersection = (predicted & actual).sum(1).float()
    union = (predicted | actual).sum(1).float()
    return {
        "mA": float(balanced.mean().item()),
        "micro_attribute_accuracy": float((predicted == actual).float().mean().item()),
        "label_macro_f1": sum(label_f1) / len(label_f1),
        "InsF1": float((2 * intersection / (predicted.sum(1) + actual.sum(1)).clamp_min(1)).mean()),
        "instance_iou": float((intersection / union.clamp_min(1)).mean()),
    }


def _teacher_logits(
    data_root: Path,
    vendor_root: Path,
    checkpoint: Path,
    device: torch.device,
    rows: tuple[int, int, int],
    batch_size: int,
    epochs: int,
) -> tuple[tuple[Tensor, Tensor, Tensor], dict[str, dict[str, float]]]:
    sys.path.insert(0, str(Path(__file__).parent.resolve()))
    from run_solider_pa100k_parquet import _extract_split, _official_bce_loss
    from run_solider_proxy_experiment import _load_backbone

    teacher = _load_backbone(vendor_root.resolve(), checkpoint.resolve())
    teacher = teacher.to(device)
    teacher.eval()
    train_features, train_labels = _extract_split(
        data_root / "train.parquet", teacher, device, batch_size, rows[0]
    )
    val_features, val_labels = _extract_split(
        data_root / "val.parquet", teacher, device, batch_size, rows[1]
    )
    test_features, test_labels = _extract_split(
        data_root / "test.parquet", teacher, device, batch_size, rows[2]
    )
    head = nn.Linear(train_features.shape[1], len(ATTRIBUTES)).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=1e-3, weight_decay=1e-4)
    ratio = train_labels.mean(dim=0)
    for _ in range(epochs):
        order = torch.randperm(train_features.shape[0])
        for start in range(0, len(order), 2048):
            index = order[start : start + 2048]
            logits = head(train_features[index].to(device))
            loss = _official_bce_loss(logits, train_labels[index].to(device), ratio)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    with torch.inference_mode():
        logits = tuple(head(item.features.to(device)).cpu() for item in (
            SplitTensors(train_features, train_labels),
            SplitTensors(val_features, val_labels),
            SplitTensors(test_features, test_labels),
        ))
    thresholds = choose_thresholds(logits[1], val_labels)
    audit = {name: metrics(value, labels, thresholds) for name, value, labels in zip(
        ("train", "val", "test"), logits, (train_labels, val_labels, test_labels), strict=True
    )}
    del teacher, head, train_features, val_features, test_features, optimizer
    torch.cuda.empty_cache()
    return logits, audit


def run(
    output: Path = Path("experiments/results/clip-vit-l14-distillation.json"),
    data_root: Path = DEFAULT_DATA_ROOT,
    clip_checkpoint: str = DEFAULT_CLIP,
    vendor_root: Path = Path("experiments/vendor/SOLIDER-PersonAttributeRecognition"),
    teacher_checkpoint: Path = Path("experiments/models/solider_swin_base.pth"),
    train_rows: int = 80_000,
    val_rows: int = 10_000,
    test_rows: int = 10_000,
    extract_batch_size: int = 2,
    head_batch_size: int = 512,
    head_epochs: int = 15,
    teacher_epochs: int = 12,
    distill_alpha: float = 0.35,
    temperature: float = 2.0,
) -> None:
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    if not 0 <= distill_alpha <= 1:
        raise ValueError("distill_alpha must be between 0 and 1")
    if temperature <= 0:
        raise ValueError("temperature must be greater than 0")
    seed = 20260723
    torch.manual_seed(seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    device = torch.device("cuda")
    teacher_logits, teacher_metrics = _teacher_logits(
        data_root, vendor_root, teacher_checkpoint, device,
        (train_rows, val_rows, test_rows), extract_batch_size, teacher_epochs,
    )
    processor = CLIPProcessor.from_pretrained(clip_checkpoint, local_files_only=True)
    clip = CLIPModel.from_pretrained(clip_checkpoint, local_files_only=True).to(device).eval()
    splits = tuple(extract_clip_split(
        data_root / name, clip, processor, device, extract_batch_size, limit
    ) for name, limit in zip(("train.parquet", "val.parquet", "test.parquet"),
                             (train_rows, val_rows, test_rows), strict=True))
    del clip
    torch.cuda.empty_cache()
    hard_head = train_head(splits[0], None, device, head_epochs, head_batch_size, 0, temperature)
    kd_head = train_head(
        splits[0], teacher_logits[0], device, head_epochs, head_batch_size,
        distill_alpha, temperature
    )
    arms = {"clip_vitl14_hard": hard_head, "clip_vitl14_solider_kd": kd_head}
    results: dict[str, dict[str, object]] = {}
    models_root = Path("experiments/models").resolve()
    models_root.mkdir(parents=True, exist_ok=True)
    for name, head in arms.items():
        with torch.inference_mode():
            validation_logits = head(splits[1].features.to(device)).cpu()
            logits = tuple(head(split.features.to(device)).cpu() for split in splits)
        thresholds = choose_thresholds(validation_logits, splits[1].labels)
        metrics_by_split = {
            label: metrics(value, split.labels, thresholds)
            for label, value, split in zip(
                ("train", "val", "test"), logits, splits, strict=True
            )
        }
        checkpoint_path = models_root / f"{output.stem}-{name}.pt"
        torch.save(
            {"state_dict": head.state_dict(), "thresholds": thresholds, "attributes": ATTRIBUTES},
            checkpoint_path,
        )
        results[name] = {
            "thresholds": [float(value) for value in thresholds],
            "metrics": metrics_by_split,
            "checkpoint": str(checkpoint_path),
            "checkpoint_sha256": sha256_file(checkpoint_path),
        }
    best_name = max(results, key=lambda name: float(results[name]["metrics"]["val"]["mA"]))
    best_test = results[best_name]["metrics"]["test"]
    artifact = {
        "status": "valid",
        "dataset": "tuandunghcmut/PA-100K official parquet split",
        "split": "official train/val/test; no identity or track IDs",
        "student_base": clip_checkpoint,
        "teacher": "SOLIDER Swin-B PAR backbone plus supervised 26-attribute head",
        "rows": {"train": train_rows, "val": val_rows, "test": test_rows},
        "device": torch.cuda.get_device_name(0),
        "runtime": {"python": platform.python_version(), "torch": torch.__version__},
        "distillation": {
            "alpha": distill_alpha,
            "temperature": temperature,
            "teacher_epochs": teacher_epochs,
        },
        "teacher_metrics": teacher_metrics,
        "arms": results,
        "selected_by_val_mA": best_name,
        "seed": seed,
        "gate": {
            "target_mA": 0.85,
            "measured_test_mA": best_test["mA"],
            "passed": float(best_test["mA"]) >= 0.85,
            "warning": "PA-100K mA is not CCTV identity or track-heldout accuracy.",
        },
        "provenance": {
            "clip_checkpoint": clip_checkpoint,
            "teacher_checkpoint_sha256": sha256_file(teacher_checkpoint),
            "script_sha256": sha256_file(Path(__file__).resolve()),
            "data_files": {
                name: {
                    "path": str((data_root / name).resolve()),
                    "bytes": (data_root / name).stat().st_size,
                }
                for name in ("train.parquet", "val.parquet", "test.parquet")
            },
        },
    }
    output = output.resolve()
    if Path.cwd().resolve() not in output.parents:
        raise ValueError("output must be inside workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    summary = {"output": str(output), "best": best_name, "test": best_test}
    typer.echo(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    typer.run(run)
