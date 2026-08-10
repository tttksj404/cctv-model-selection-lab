# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow", "pyarrow", "torch"]
# ///
from __future__ import annotations

import argparse
import io
import json
import platform
import random
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as parquet
import torch
from PIL import Image
from run_solider_pa100k_parquet import ATTRIBUTES, _extract_split, _metrics, _official_bce_loss
from run_solider_simuletic_method_sweep import ExperimentRuntimeError, _load_backbone, _load_head
from solider_simuletic_sweep_data import (
    feature_rows,
    group_metrics,
    group_split,
    image_tensor,
    load_simuletic,
    masked_metrics,
    sha256_file,
)
from torch import Tensor, nn


def _pa_image(value: dict[str, Any]) -> Tensor:
    with Image.open(io.BytesIO(value["bytes"])) as image:
        image = image.convert("RGB").resize((128, 256), Image.Resampling.BICUBIC)
        array = np.asarray(image, dtype=np.float32) / 255.0
    mean = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
    std = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)
    return (torch.from_numpy(array).permute(2, 0, 1) - mean) / std


def _asl_loss(logits: Tensor, targets: Tensor, mask: Tensor) -> Tensor:
    probabilities = logits.sigmoid()
    positive = probabilities
    negative = (1.0 - probabilities + 0.05).clamp(max=1.0)
    log_probability = targets * torch.log(positive.clamp_min(1e-8)) + (1 - targets) * torch.log(negative.clamp_min(1e-8))
    probability = positive * targets + negative * (1 - targets)
    gamma = 1.0 * targets + 4.0 * (1 - targets)
    values = -log_probability * (1 - probability).pow(gamma) * mask
    return values.sum() / mask.to(dtype=values.dtype).sum().clamp_min(1.0)


def _pa_epoch(
    backbone: nn.Module,
    head: nn.Module,
    path: Path,
    max_rows: int,
    batch_size: int,
    optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler,
    device: torch.device,
) -> float:
    ratio: Tensor | None = None
    losses: list[float] = []
    seen = 0
    columns = ["image", *ATTRIBUTES]
    for batch in parquet.ParquetFile(path).iter_batches(batch_size=batch_size, columns=columns):
        rows = batch.to_pydict()
        count = min(len(rows["image"]), max_rows - seen)
        images = torch.stack([_pa_image(rows["image"][index]) for index in range(count)]).to(device)
        labels = torch.tensor([[int(rows[name][index]) for name in ATTRIBUTES] for index in range(count)], dtype=torch.float32, device=device)
        if ratio is None:
            ratio = labels.mean(dim=0)
        backbone.train()
        head.train()
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            features = nn.functional.adaptive_avg_pool2d(backbone(images), 1).flatten(1)
            loss = _official_bce_loss(head(features), labels, ratio)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        losses.append(float(loss.detach().item()))
        seen += count
        if seen >= max_rows:
            break
    if not losses:
        raise ExperimentRuntimeError("no PA-100K rows trained")
    return sum(losses) / len(losses)


def _simu_epoch(
    backbone: nn.Module,
    head: nn.Module,
    rows: tuple[dict[str, Any], ...],
    batch_size: int,
    optimizer: torch.optim.Optimizer,
    scaler: torch.amp.GradScaler,
    device: torch.device,
) -> float:
    losses: list[float] = []
    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        images = torch.stack([image_tensor(row["image"]) for row in chunk]).to(device)
        labels = torch.stack([row["labels"] for row in chunk]).to(device)
        masks = torch.stack([row["mask"] for row in chunk]).to(device)
        backbone.train()
        head.train()
        with torch.autocast(device_type="cuda", dtype=torch.float16):
            features = nn.functional.adaptive_avg_pool2d(backbone(images), 1).flatten(1)
            loss = _asl_loss(head(features), labels, masks)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.step(optimizer)
        scaler.update()
        losses.append(float(loss.detach().item()))
    return sum(losses) / max(1, len(losses))


def run(args: argparse.Namespace) -> None:
    if not torch.cuda.is_available():
        raise ExperimentRuntimeError("CUDA is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    checkpoint = args.checkpoint.resolve()
    backbone = _load_backbone(args.vendor_root.resolve(), checkpoint).to(device)
    backbone.eval()
    base_head = _load_head(args.base_head.resolve(), 1024, device)
    optimizer = torch.optim.AdamW([
        {"params": backbone.parameters(), "lr": args.backbone_lr},
        {"params": base_head.parameters(), "lr": args.head_lr},
    ], weight_decay=0.0001)
    scaler = torch.amp.GradScaler("cuda")
    simu_rows = load_simuletic(args.simu_root.resolve(), args.simu_metadata.resolve())
    train_ids, _val_ids, test_ids = group_split(simu_rows)
    train_rows = tuple(row for row in simu_rows if int(row["identity"]) in train_ids)
    test_indices = tuple(index for index, row in enumerate(simu_rows) if int(row["identity"]) in test_ids)
    losses: list[dict[str, float]] = []
    for epoch in range(args.epochs):
        pa_loss = _pa_epoch(backbone, base_head, args.data_root.resolve() / "train.parquet", args.pa_train_rows, args.batch_size, optimizer, scaler, device)
        simu_loss = _simu_epoch(backbone, base_head, train_rows, args.batch_size, optimizer, scaler, device)
        losses.append({"epoch": float(epoch + 1), "pa_loss": pa_loss, "simu_asl_loss": simu_loss})
    backbone.eval()
    base_head.eval()
    pa_val_features, pa_val_labels = _extract_split(args.data_root.resolve() / "val.parquet", backbone, device, args.extract_batch_size, args.pa_val_rows)
    pa_test_features, pa_test_labels = _extract_split(args.data_root.resolve() / "test.parquet", backbone, device, args.extract_batch_size, args.pa_test_rows)
    simu_features = feature_rows(backbone, simu_rows, device, args.extract_batch_size)
    simu_labels = torch.stack([row["labels"] for row in simu_rows])
    simu_masks = torch.stack([row["mask"] for row in simu_rows])
    with torch.inference_mode():
        pa_val_logits = base_head(pa_val_features.to(device)).float().cpu()
        pa_test_logits = base_head(pa_test_features.to(device)).float().cpu()
        simu_logits = base_head(simu_features.to(device)).float().cpu()
    result = {
        "status": "measured",
        "model": "SOLIDER Swin-B backbone plus PA-100K head end-to-end fine-tuning",
        "method": "PA-100K weighted BCE epoch followed by masked Simuletic ASL epoch; no response-level teacher labels",
        "rows": {"pa_train": args.pa_train_rows, "pa_val": args.pa_val_rows, "pa_test": args.pa_test_rows, "simuletic_train": len(train_rows), "simuletic_total": len(simu_rows), "simuletic_train_groups": sorted(train_ids), "simuletic_test_groups": sorted(test_ids)},
        "metrics": {"pa100k": {"val": _metrics(pa_val_logits, pa_val_labels), "test": _metrics(pa_test_logits, pa_test_labels)}, "simuletic": {"all": masked_metrics(simu_logits, simu_labels, simu_masks), "image_heldout": masked_metrics(simu_logits[list(test_indices)], simu_labels[list(test_indices)], simu_masks[list(test_indices)]), "group_heldout": group_metrics(simu_logits, simu_rows, test_indices)}},
        "runtime": {"device": torch.cuda.get_device_name(0), "torch": torch.__version__, "python": platform.python_version(), "seed": args.seed, "epochs": args.epochs, "backbone_lr": args.backbone_lr, "head_lr": args.head_lr, "batch_size": args.batch_size, "losses": losses},
        "provenance": {"script_sha256": sha256_file(Path(__file__).resolve()), "solider_checkpoint_sha256": sha256_file(checkpoint), "base_head_sha256": sha256_file(args.base_head.resolve()), "simu_metadata_sha256": sha256_file(args.simu_metadata.resolve())},
        "metric_warning": "Simuletic is a synthetic CCTV attribute proxy and does not establish project CCTV identity accuracy.",
    }
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"backbone": backbone.state_dict(), "head": base_head.state_dict(), "attributes": list(ATTRIBUTES), "provenance": result["provenance"]}, output.with_suffix(".pt"))
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "metrics": result["metrics"]}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--vendor-root", type=Path, required=True)
    parser.add_argument("--base-head", type=Path, required=True)
    parser.add_argument("--simu-root", type=Path, required=True)
    parser.add_argument("--simu-metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pa-train-rows", type=int, default=80000)
    parser.add_argument("--pa-val-rows", type=int, default=10000)
    parser.add_argument("--pa-test-rows", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--extract-batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--backbone-lr", type=float, default=1e-5)
    parser.add_argument("--head-lr", type=float, default=1e-4)
    parser.add_argument("--seed", type=int, default=20260727)
    run(parser.parse_args())


if __name__ == "__main__":
    main()

