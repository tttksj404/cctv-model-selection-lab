from __future__ import annotations

import argparse
import io
import json
import platform
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pyarrow.parquet as parquet
import torch
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional as F

sys.path.insert(0, str(Path(__file__).parent.resolve()))
from run_solider_proxy_experiment import _hash_file, _load_backbone

ATTRIBUTES = (
    "Female",
    "AgeOver60",
    "Age18-60",
    "AgeLess18",
    "Front",
    "Side",
    "Back",
    "Hat",
    "Glasses",
    "HandBag",
    "ShoulderBag",
    "Backpack",
    "HoldObjectsInFront",
    "ShortSleeve",
    "LongSleeve",
    "UpperStride",
    "UpperLogo",
    "UpperPlaid",
    "UpperSplice",
    "LowerStripe",
    "LowerPattern",
    "LongCoat",
    "Trousers",
    "Shorts",
    "Skirt&Dress",
    "boots",
)
MEAN = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
STD = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)


class ExperimentRuntimeError(RuntimeError):
    pass


class ExperimentOutputError(ValueError):
    pass


def _image_tensor(value: dict) -> Tensor:
    raw = value.get("bytes")
    if raw is None:
        raise ExperimentRuntimeError("parquet image bytes are missing")
    with Image.open(io.BytesIO(raw)) as image:
        image = image.convert("RGB").resize((128, 256), Image.Resampling.BICUBIC)
        array = np.asarray(image, dtype=np.float32) / 255.0
    return (torch.from_numpy(array).permute(2, 0, 1) - MEAN) / STD


def _extract_split(
    path: Path, model: nn.Module, device: torch.device, batch_size: int, max_rows: int
) -> tuple[Tensor, Tensor]:
    columns = ["image", *ATTRIBUTES]
    feature_chunks = []
    label_chunks = []
    seen = 0
    with ThreadPoolExecutor(max_workers=8) as decode_pool, torch.inference_mode():
        for batch in parquet.ParquetFile(path).iter_batches(batch_size=batch_size, columns=columns):
            rows = batch.to_pydict()
            count = min(len(rows["image"]), max_rows - seen)
            images = torch.stack(
                list(decode_pool.map(_image_tensor, rows["image"][:count]))
            ).to(device)
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                output = model(images)
            feature_chunks.append(
                nn.functional.adaptive_avg_pool2d(output, 1).flatten(1).float().cpu()
            )
            label_chunks.append(
                torch.tensor(
                    [[int(rows[name][index]) for name in ATTRIBUTES] for index in range(count)],
                    dtype=torch.float32,
                )
            )
            seen += count
            if seen >= max_rows:
                break
    if not feature_chunks:
        raise ExperimentRuntimeError(f"no rows extracted from {path}")
    return torch.cat(feature_chunks), torch.cat(label_chunks)


def _metrics(logits: Tensor, labels: Tensor) -> dict[str, float]:
    predictions = logits.sigmoid().ge(0.5)
    positives = labels.ge(0.5)
    negative = ~positives
    positive_count = positives.sum(dim=0)
    negative_count = negative.sum(dim=0)
    positive_accuracy = (predictions & positives).sum(dim=0).float() / positive_count.clamp_min(1)
    negative_accuracy = ((~predictions) & negative).sum(dim=0).float() / negative_count.clamp_min(1)
    instance_intersection = (predictions & positives).sum(dim=1).float()
    instance_prediction_count = predictions.sum(dim=1).float()
    instance_target_count = positives.sum(dim=1).float()
    instance_union = (predictions | positives).sum(dim=1).float()
    instance_precision = (instance_intersection / instance_prediction_count.clamp_min(1e-20)).mean()
    instance_recall = (instance_intersection / instance_target_count.clamp_min(1e-20)).mean()
    instance_f1 = (
        2
        * instance_precision
        * instance_recall
        / (instance_precision + instance_recall).clamp_min(1e-20)
    )
    label_f1 = []
    for index in range(labels.shape[1]):
        tp = ((predictions[:, index]) & positives[:, index]).sum().float()
        fp = ((predictions[:, index]) & negative[:, index]).sum().float()
        fn = ((~predictions[:, index]) & positives[:, index]).sum().float()
        label_f1.append(float((2 * tp / (2 * tp + fp + fn).clamp_min(1)).item()))
    return {
        "mA": float(((positive_accuracy + negative_accuracy) / 2).mean().item()),
        "instance_acc": float(
            (instance_intersection / instance_union.clamp_min(1e-20)).mean().item()
        ),
        "instance_precision": float(instance_precision.item()),
        "instance_recall": float(instance_recall.item()),
        "InsF1": float(instance_f1.item()),
        "label_macro_f1": float(sum(label_f1) / len(label_f1)),
    }


def _official_bce_loss(logits: Tensor, targets: Tensor, label_ratio: Tensor) -> Tensor:
    ratio = label_ratio.to(device=logits.device, dtype=logits.dtype)
    weights = torch.exp(targets * (1 - ratio) + (1 - targets) * ratio)
    loss_matrix = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    return (loss_matrix * weights).sum(dim=1).mean()


def _train(
    features: Tensor, labels: Tensor, epochs: int, batch_size: int, device: torch.device
) -> nn.Module:
    head = nn.Linear(features.shape[1], labels.shape[1]).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.001, weight_decay=0.0001)
    label_ratio = labels.mean(dim=0)
    for _ in range(epochs):
        order = torch.randperm(features.shape[0])
        head.train()
        for start in range(0, len(order), batch_size):
            indices = order[start : start + batch_size]
            logits = head(features[indices].to(device))
            loss = _official_bce_loss(logits, labels[indices].to(device), label_ratio)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def _evaluate(
    head: nn.Module, features: Tensor, labels: Tensor, device: torch.device, batch_size: int
) -> dict[str, float]:
    logits = []
    with torch.inference_mode():
        for start in range(0, features.shape[0], batch_size):
            logits.append(head(features[start : start + batch_size].to(device)).cpu())
    return _metrics(torch.cat(logits), labels)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("experiments/data/pa100k_full"))
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("experiments/models/solider_swin_base.pth")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/results/solider-pa100k-head-only.json")
    )
    parser.add_argument("--train-rows", type=int, default=80000)
    parser.add_argument("--val-rows", type=int, default=10000)
    parser.add_argument("--test-rows", type=int, default=10000)
    parser.add_argument("--extract-batch-size", type=int, default=4)
    parser.add_argument("--head-batch-size", type=int, default=2048)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--head-output", type=Path, default=None)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise ExperimentRuntimeError("CUDA is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    model = _load_backbone(args.checkpoint.resolve()).to(device)
    model.eval()
    train_features, train_labels = _extract_split(
        args.data_root / "train.parquet", model, device, args.extract_batch_size, args.train_rows
    )
    val_features, val_labels = _extract_split(
        args.data_root / "val.parquet", model, device, args.extract_batch_size, args.val_rows
    )
    test_features, test_labels = _extract_split(
        args.data_root / "test.parquet", model, device, args.extract_batch_size, args.test_rows
    )
    del model
    torch.cuda.empty_cache()
    head = _train(train_features, train_labels, args.epochs, args.head_batch_size, device)
    result = {
        "status": "valid",
        "model": "SOLIDER Swin-B frozen backbone plus PA-100K 26-attribute linear head",
        "dataset": "tuandunghcmut/PA-100K parquet",
        "rows": {"train": len(train_labels), "val": len(val_labels), "test": len(test_labels)},
        "attributes": list(ATTRIBUTES),
        "split": "official train/val/test; no identity or track IDs",
        "seed": args.seed,
        "head_epochs": args.epochs,
        "extract_batch_size": args.extract_batch_size,
        "head_batch_size": args.head_batch_size,
        "loss": "SOLIDER official ratio2weight BCE loss",
        "label_positive_ratio": [float(value) for value in train_labels.mean(dim=0)],
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "python": platform.python_version(),
        "checkpoint_sha256": _hash_file(args.checkpoint.resolve()),
        "metrics": {
            "train": _evaluate(head, train_features, train_labels, device, args.head_batch_size),
            "val": _evaluate(head, val_features, val_labels, device, args.head_batch_size),
            "test": _evaluate(head, test_features, test_labels, device, args.head_batch_size),
        },
        "metric_warning": (
            "This head-only experiment is not the official end-to-end SOLIDER "
            "fine-tuning recipe and is not CCTV track accuracy."
        ),
    }
    output = args.output.resolve()
    workspace = Path.cwd().resolve()
    if workspace not in output.parents:
        raise ExperimentOutputError("output must be inside workspace")
    if args.head_output is not None:
        head_output = args.head_output.resolve()
        if workspace not in head_output.parents:
            raise ExperimentOutputError("head output must be inside workspace")
        if head_output == output:
            raise ExperimentOutputError("output and head output must be different files")
        head_output.parent.mkdir(parents=True, exist_ok=True)
        torch.save(
            {
                "state_dict": head.state_dict(),
                "attributes": list(ATTRIBUTES),
                "source": "solider-pa100k-head-only",
                "rows": {
                    "train": len(train_labels),
                    "val": len(val_labels),
                    "test": len(test_labels),
                },
                "seed": args.seed,
            },
            head_output,
        )
        result["head_checkpoint"] = str(head_output)
        result["head_checkpoint_sha256"] = _hash_file(head_output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": result["metrics"], "rows": result["rows"]}))


if __name__ == "__main__":
    main()

