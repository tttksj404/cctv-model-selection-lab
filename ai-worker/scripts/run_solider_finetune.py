#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "pyarrow", "torch"]
# ///

# How to run
# 1. Install uv (if not installed):
#      curl -LsSf https://astral.sh/uv/install.sh | sh
# 2. Run directly (no venv, no pip install needed):
#      uv run run_solider_finetune.py --help
# 3. Or make executable and run:
#      chmod +x run_solider_finetune.py && ./run_solider_finetune.py

from __future__ import annotations

import argparse
import json
import platform
import random
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pyarrow.parquet as parquet
import torch
from run_solider_pa100k_parquet import (
    ATTRIBUTES,
    _hash_file,
    _image_tensor,
    _load_backbone,
    _metrics,
    _official_bce_loss,
)
from torch import Tensor, nn


class ExperimentRuntimeError(RuntimeError):
    pass


class ExperimentOutputError(ValueError):
    pass


def _label_rows(path: Path, max_rows: int) -> Tensor:
    labels = []
    seen = 0
    for batch in parquet.ParquetFile(path).iter_batches(batch_size=4096, columns=list(ATTRIBUTES)):
        rows = batch.to_pydict()
        count = min(len(rows[ATTRIBUTES[0]]), max_rows - seen)
        labels.extend([[int(rows[name][index]) for name in ATTRIBUTES] for index in range(count)])
        seen += count
        if seen >= max_rows:
            break
    if not labels:
        raise ExperimentRuntimeError(f"no labels extracted from {path}")
    return torch.tensor(labels, dtype=torch.float32)


def _batches(
    path: Path, max_rows: int, batch_size: int, device: torch.device
) -> Iterator[tuple[Tensor, Tensor]]:
    columns = ["image", *ATTRIBUTES]
    seen = 0
    for batch in parquet.ParquetFile(path).iter_batches(batch_size=batch_size, columns=columns):
        rows = batch.to_pydict()
        count = min(len(rows["image"]), max_rows - seen)
        images = torch.stack([_image_tensor(rows["image"][index]) for index in range(count)])
        labels = torch.tensor(
            [[int(rows[name][index]) for name in ATTRIBUTES] for index in range(count)],
            dtype=torch.float32,
        )
        yield images.to(device), labels.to(device)
        seen += count
        if seen >= max_rows:
            break


def _features(backbone: nn.Module, images: Tensor) -> Tensor:
    return nn.functional.adaptive_avg_pool2d(backbone(images), 1).flatten(1)


def _evaluate(
    backbone: nn.Module,
    head: nn.Module,
    path: Path,
    rows: int,
    batch_size: int,
    device: torch.device,
) -> dict[str, float]:
    logits = []
    labels = []
    backbone.eval()
    head.eval()
    with torch.inference_mode():
        for images, targets in _batches(path, rows, batch_size, device):
            logits.append(head(_features(backbone, images)).float().cpu())
            labels.append(targets.cpu())
    return _metrics(torch.cat(logits), torch.cat(labels))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("experiments/data/pa100k_full"))
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("experiments/models/solider_swin_base.pth")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/results/solider-finetune-smoke.json")
    )
    parser.add_argument("--train-rows", type=int, default=1000)
    parser.add_argument("--val-rows", type=int, default=500)
    parser.add_argument("--test-rows", type=int, default=500)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=1e-5)
    parser.add_argument("--head-learning-rate", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise ExperimentRuntimeError("CUDA is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    train_path = args.data_root / "train.parquet"
    val_path = args.data_root / "val.parquet"
    test_path = args.data_root / "test.parquet"
    train_labels = _label_rows(train_path, args.train_rows)
    label_ratio = train_labels.mean(dim=0)
    backbone = _load_backbone(args.checkpoint.resolve()).to(device)
    head = nn.Linear(1024, len(ATTRIBUTES)).to(device)
    optimizer = torch.optim.AdamW(
        [
            {"params": backbone.parameters(), "lr": args.learning_rate},
            {"params": head.parameters(), "lr": args.head_learning_rate},
        ],
        weight_decay=0.0,
    )
    scaler = torch.amp.GradScaler("cuda")
    for _ in range(args.epochs):
        backbone.train()
        head.train()
        for images, targets in _batches(train_path, args.train_rows, args.batch_size, device):
            with torch.autocast(device_type="cuda", dtype=torch.float16):
                loss = _official_bce_loss(
                    head(_features(backbone, images)), targets, label_ratio.to(device)
                )
            optimizer.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.step(optimizer)
            scaler.update()
    metrics = {
        "train": _evaluate(backbone, head, train_path, args.train_rows, args.batch_size, device),
        "val": _evaluate(backbone, head, val_path, args.val_rows, args.batch_size, device),
        "test": _evaluate(backbone, head, test_path, args.test_rows, args.batch_size, device),
    }
    result = {
        "status": "valid",
        "model": "SOLIDER Swin-B end-to-end fine-tuning with linear PA-100K head",
        "dataset": "tuandunghcmut/PA-100K parquet",
        "rows": {"train": args.train_rows, "val": args.val_rows, "test": args.test_rows},
        "attributes": list(ATTRIBUTES),
        "seed": args.seed,
        "epochs": args.epochs,
        "batch_size": args.batch_size,
        "learning_rate": args.learning_rate,
        "head_learning_rate": args.head_learning_rate,
        "loss": "SOLIDER official ratio2weight BCE loss",
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "python": platform.python_version(),
        "checkpoint_sha256": _hash_file(args.checkpoint.resolve()),
        "metrics": metrics,
        "metric_warning": "This is PA-100K attribute accuracy, not CCTV track identity accuracy.",
    }
    output = args.output.resolve()
    if Path.cwd().resolve() not in output.parents:
        raise ExperimentOutputError("output must be inside workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": metrics, "rows": result["rows"]}))


if __name__ == "__main__":
    main()
