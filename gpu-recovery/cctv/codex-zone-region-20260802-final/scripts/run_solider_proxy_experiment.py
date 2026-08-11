from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
import sys
import types
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from torch import Tensor, nn

FIELD_NAMES = (
    "gender",
    "age",
    "viewpoint",
    "accessory_present",
    "sleeve",
    "bottom_type",
)
FIELD_CLASSES = {
    "gender": ("male", "female"),
    "age": ("under18", "18_60", "over60"),
    "viewpoint": ("front", "side", "back"),
    "accessory_present": ("absent", "present"),
    "sleeve": ("short", "long", "other"),
    "bottom_type": ("trousers", "shorts", "skirt_dress", "other"),
}
IMAGENET_MEAN = torch.tensor((0.485, 0.456, 0.406)).view(3, 1, 1)
IMAGENET_STD = torch.tensor((0.229, 0.224, 0.225)).view(3, 1, 1)


def _install_optional_stubs() -> None:
    if "mmcv.runner" not in sys.modules:
        mmcv = types.ModuleType("mmcv")
        runner = types.ModuleType("mmcv.runner")
        runner.load_checkpoint = lambda *args, **kwargs: None
        mmcv.runner = runner
        sys.modules["mmcv"] = mmcv
        sys.modules["mmcv.runner"] = runner
    if "cv2" not in sys.modules:
        sys.modules["cv2"] = types.ModuleType("cv2")


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _field_index(field: str, value: str) -> int:
    return FIELD_CLASSES[field].index(value)


def _labels(record: dict) -> tuple[int, ...]:
    labels = record["labels"]
    age = (
        "over60"
        if labels.get("AgeOver60", 0)
        else "under18"
        if labels.get("AgeLess18", 0)
        else "18_60"
    )
    viewpoint = "front" if labels.get("Front", 0) else "side" if labels.get("Side", 0) else "back"
    sleeve = (
        "short"
        if labels.get("ShortSleeve", 0)
        else "long"
        if labels.get("LongSleeve", 0)
        else "other"
    )
    bottom = (
        "trousers"
        if labels.get("Trousers", 0)
        else "shorts"
        if labels.get("Shorts", 0)
        else "skirt_dress"
        if labels.get("SkirtDress", 0) or labels.get("Skirt&Dress", 0)
        else "other"
    )
    values = (
        "female" if labels.get("Female", 0) else "male",
        age,
        viewpoint,
        "present"
        if any(
            labels.get(name, 0) for name in ("Hat", "Glasses", "HandBag", "ShoulderBag", "Backpack")
        )
        else "absent",
        sleeve,
        bottom,
    )
    return tuple(
        _field_index(field, value) for field, value in zip(FIELD_NAMES, values, strict=True)
    )


def _read_examples(dataset_root: Path, limit: int) -> tuple[tuple[Path, tuple[int, ...]], ...]:
    examples = []
    with (dataset_root / "manifest.jsonl").open(encoding="utf-8") as stream:
        for raw in stream:
            if len(examples) >= limit:
                break
            record = json.loads(raw)
            image = (dataset_root / record["image_name"]).resolve()
            if image.is_file():
                examples.append((image, _labels(record)))
    if len(examples) < 20:
        raise RuntimeError(f"too few examples: {len(examples)}")
    return tuple(examples)


def _pixels(path: Path) -> Tensor:
    with Image.open(path) as image:
        image = image.convert("RGB").resize((128, 256), Image.Resampling.BICUBIC)
        array = np.asarray(image, dtype=np.float32) / 255.0
    tensor = torch.from_numpy(array).permute(2, 0, 1)
    return (tensor - IMAGENET_MEAN) / IMAGENET_STD


def _extract_features(
    backbone: nn.Module,
    examples: tuple[tuple[Path, tuple[int, ...]], ...],
    batch_size: int,
    device: torch.device,
) -> Tensor:
    features = []
    backbone.eval()
    with torch.inference_mode():
        for start in range(0, len(examples), batch_size):
            batch = torch.stack(
                [_pixels(path) for path, _ in examples[start : start + batch_size]]
            ).to(device)
            output = backbone(batch)
            features.append(nn.functional.adaptive_avg_pool2d(output, 1).flatten(1).cpu())
    return torch.cat(features, dim=0)


def _folds(
    count: int, fold_count: int, seed: int
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    generator = torch.Generator().manual_seed(seed)
    shuffled = torch.randperm(count, generator=generator).tolist()
    return tuple(
        (
            tuple(index for index in shuffled if index not in set(shuffled[fold::fold_count])),
            tuple(shuffled[fold::fold_count]),
        )
        for fold in range(fold_count)
    )


class MultiHead(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.heads = nn.ModuleList(
            nn.Linear(input_dim, len(FIELD_CLASSES[field])) for field in FIELD_NAMES
        )

    def forward(self, features: Tensor) -> tuple[Tensor, ...]:
        return tuple(head(features) for head in self.heads)


def _metrics(logits: tuple[Tensor, ...], labels: Tensor) -> dict[str, object]:
    predictions = torch.stack(tuple(output.argmax(dim=1) for output in logits), dim=1)
    hits = predictions.eq(labels)
    field_accuracy = hits.float().mean(dim=0).tolist()
    class_f1 = []
    for field_index, field in enumerate(FIELD_NAMES):
        per_class = []
        for class_index in range(len(FIELD_CLASSES[field])):
            predicted = predictions[:, field_index] == class_index
            actual = labels[:, field_index] == class_index
            tp = int((predicted & actual).sum())
            fp = int((predicted & ~actual).sum())
            fn = int((~predicted & actual).sum())
            denominator = 2 * tp + fp + fn
            per_class.append(2 * tp / denominator if denominator else 0.0)
        class_f1.append(sum(per_class) / len(per_class))
    return {
        "field_accuracy": [float(value) for value in field_accuracy],
        "attribute_accuracy": float(sum(field_accuracy) / len(field_accuracy)),
        "macro_f1": float(sum(class_f1) / len(class_f1)),
        "sample_all_field_exact": float(hits.all(dim=1).float().mean()),
    }


def _train_head(
    features: Tensor,
    labels: Tensor,
    train_indices: tuple[int, ...],
    validation_indices: tuple[int, ...],
    epochs: int,
    seed: int,
) -> tuple[dict[str, object], dict[str, object]]:
    torch.manual_seed(seed)
    head = MultiHead(features.shape[1])
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.01, weight_decay=0.01)
    train = torch.tensor(train_indices)
    validation = torch.tensor(validation_indices)
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        outputs = head(features[train])
        loss = sum(
            nn.functional.cross_entropy(output, labels[train, index])
            for index, output in enumerate(outputs)
        )
        loss.backward()
        optimizer.step()
    head.eval()
    with torch.inference_mode():
        train_metrics = _metrics(head(features[train]), labels[train])
        validation_metrics = _metrics(head(features[validation]), labels[validation])
    return train_metrics, validation_metrics


def _trusted_vendor_root() -> Path:
    vendor_root = (
        Path(__file__).resolve().parents[1]
        / "experiments"
        / "vendor"
        / "SOLIDER-PersonAttributeRecognition"
    ).resolve()
    marker = vendor_root / "models" / "backbone" / "swin_transformer.py"
    if not marker.is_file():
        raise RuntimeError("repository-pinned SOLIDER vendor tree is unavailable")
    return vendor_root


def _load_backbone(checkpoint: Path) -> nn.Module:
    _install_optional_stubs()
    vendor_root = _trusted_vendor_root()
    sys.path.insert(0, str(vendor_root))
    from models.backbone import swin_transformer

    torch_load = torch.load

    def load_trusted_checkpoint(*args, **kwargs):
        kwargs.setdefault("weights_only", True)
        return torch_load(*args, **kwargs)

    torch.load = load_trusted_checkpoint
    try:
        return swin_transformer.swin_base_patch4_window7_224(
            pretrained=str(checkpoint), semantic_weight=0.8
        )
    finally:
        torch.load = torch_load


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset-root", type=Path, default=Path("experiments/data/cctv_proxy/pa100k")
    )
    parser.add_argument(
        "--checkpoint", type=Path, default=Path("experiments/models/solider_swin_base.pth")
    )
    parser.add_argument(
        "--output", type=Path, default=Path("experiments/results/solider-swin-b-proxy.json")
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--epochs", type=int, default=120)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the SOLIDER semantic backbone")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    examples = _read_examples(args.dataset_root, args.limit)
    labels = torch.tensor([item[1] for item in examples], dtype=torch.long)
    backbone = _load_backbone(args.checkpoint.resolve()).to(device)
    features = _extract_features(backbone, examples, args.batch_size, device)
    del backbone
    torch.cuda.empty_cache()
    fold_results = []
    for fold, (train_indices, validation_indices) in enumerate(
        _folds(len(examples), args.folds, args.seed)
    ):
        train_metrics, validation_metrics = _train_head(
            features, labels, train_indices, validation_indices, args.epochs, args.seed + fold
        )
        fold_results.append(
            {"fold": fold, "train": train_metrics, "validation": validation_metrics}
        )
    validation = [item["validation"] for item in fold_results]
    aggregate = {
        "attribute_accuracy": float(
            sum(item["attribute_accuracy"] for item in validation) / len(validation)
        ),
        "macro_f1": float(sum(item["macro_f1"] for item in validation) / len(validation)),
        "sample_all_field_exact": float(
            sum(item["sample_all_field_exact"] for item in validation) / len(validation)
        ),
        "field_accuracy": [
            float(sum(item["field_accuracy"][index] for item in validation) / len(validation))
            for index in range(len(FIELD_NAMES))
        ],
    }
    result = {
        "status": "valid",
        "model": "SOLIDER Swin-B frozen backbone plus supervised six-field linear head",
        "dataset": "PA-100K local proxy subset",
        "examples": len(examples),
        "split": "deterministic image-level 5-fold; no identity or track IDs",
        "seed": args.seed,
        "head_epochs": args.epochs,
        "batch_size": args.batch_size,
        "device": torch.cuda.get_device_name(0),
        "torch": torch.__version__,
        "python": platform.python_version(),
        "checkpoint_sha256": _hash_file(args.checkpoint.resolve()),
        "fields": list(FIELD_NAMES),
        "aggregate_validation": aggregate,
        "folds": fold_results,
        "metric_warning": (
            "This is not PA-100K mA, not sample-level exact match, not track-level "
            "exact match, and not CCTV identity accuracy."
        ),
    }
    output = args.output.resolve()
    workspace = Path.cwd().resolve()
    if workspace not in output.parents:
        raise ValueError("output must be inside workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "aggregate_validation": aggregate,
                "examples": len(examples),
                "device": torch.cuda.get_device_name(0),
            }
        )
    )


if __name__ == "__main__":
    main()
