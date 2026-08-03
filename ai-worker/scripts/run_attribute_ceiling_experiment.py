from __future__ import annotations

import argparse
import hashlib
import json
import platform
import random
from dataclasses import asdict, dataclass
from pathlib import Path

import torch
import transformers
from PIL import Image
from pydantic import BaseModel, ConfigDict, StrictInt, field_validator
from torch import Tensor, nn
from transformers import CLIPModel, CLIPProcessor

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
MAX_IMAGE_PIXELS = 40_000_000


class PaRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    image_name: str
    image_url: str | None = None
    labels: dict[str, StrictInt]

    @field_validator("labels")
    @classmethod
    def validate_binary_labels(cls, labels: dict[str, StrictInt]) -> dict[str, StrictInt]:
        if any(value not in (0, 1) for value in labels.values()):
            raise ValueError("labels must contain only 0 or 1")
        return labels


@dataclass(frozen=True, slots=True)
class Example:
    image: Path
    labels: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Metrics:
    attribute_accuracy: float
    macro_f1: float
    field_accuracy: tuple[float, ...]


class MultiHead(nn.Module):
    def __init__(self, input_dim: int) -> None:
        super().__init__()
        self.heads = nn.ModuleList(
            nn.Linear(input_dim, len(FIELD_CLASSES[field])) for field in FIELD_NAMES
        )

    def forward(self, features: Tensor) -> tuple[Tensor, ...]:
        return tuple(head(features) for head in self.heads)


def _flag(labels: dict[str, int], *names: str) -> bool:
    return any(labels.get(name, 0) == 1 for name in names)


def _index(field: str, value: str) -> int:
    return FIELD_CLASSES[field].index(value)


def _labels(record: PaRecord) -> tuple[int, ...]:
    labels = record.labels
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
        if _flag(labels, "Hat", "Glasses", "HandBag", "ShoulderBag", "Backpack")
        else "absent",
        sleeve,
        bottom,
    )
    return tuple(_index(field, value) for field, value in zip(FIELD_NAMES, values, strict=True))


def read_examples(root: Path, limit: int) -> tuple[Example, ...]:
    if limit <= 0:
        raise ValueError("limit must be positive")
    root = root.resolve()
    manifest = root / "manifest.jsonl"
    examples: list[Example] = []
    with manifest.open(encoding="utf-8") as stream:
        for raw in stream:
            if len(examples) >= limit:
                break
            if not raw.strip():
                continue
            record = PaRecord.model_validate_json(raw)
            image = (root / record.image_name).resolve()
            if root not in image.parents:
                raise ValueError(f"image path escapes dataset root: {record.image_name}")
            if image.is_file():
                examples.append(Example(image=image, labels=_labels(record)))
    if len(examples) < 20:
        raise RuntimeError(f"too few usable examples: {len(examples)}")
    return tuple(examples)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_output_path(path: Path) -> Path:
    workspace = Path.cwd().resolve()
    output = path.resolve()
    if workspace not in output.parents:
        raise ValueError("output must be inside the current workspace")
    return output


def load_pixels(examples: tuple[Example, ...], processor: CLIPProcessor) -> Tensor:
    images: list[Image.Image] = []
    for example in examples:
        with Image.open(example.image) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError(f"image is too large: {example.image}")
            images.append(image.convert("RGB"))
    inputs = processor(images=images, return_tensors="pt")
    return inputs["pixel_values"]


def folds(
    count: int, fold_count: int, seed: int
) -> tuple[tuple[tuple[int, ...], tuple[int, ...]], ...]:
    generator = torch.Generator().manual_seed(seed)
    shuffled = torch.randperm(count, generator=generator).tolist()
    result: list[tuple[tuple[int, ...], tuple[int, ...]]] = []
    for fold in range(fold_count):
        validation = tuple(shuffled[fold::fold_count])
        validation_set = set(validation)
        training = tuple(index for index in shuffled if index not in validation_set)
        result.append((training, validation))
    return tuple(result)


def metric(logits: tuple[Tensor, ...], labels: Tensor) -> Metrics:
    predictions = torch.stack(tuple(output.argmax(dim=1) for output in logits), dim=1)
    hits = predictions.eq(labels)
    field_accuracy = tuple(float(value) for value in hits.float().mean(dim=0).cpu().tolist())
    macro_f1_values: list[float] = []
    for field_index, field in enumerate(FIELD_NAMES):
        field_predictions = predictions[:, field_index]
        field_labels = labels[:, field_index]
        class_scores: list[float] = []
        for class_index in range(len(FIELD_CLASSES[field])):
            true_positive = int(
                ((field_predictions == class_index) & (field_labels == class_index)).sum()
            )
            false_positive = int(
                ((field_predictions == class_index) & (field_labels != class_index)).sum()
            )
            false_negative = int(
                ((field_predictions != class_index) & (field_labels == class_index)).sum()
            )
            denominator = 2 * true_positive + false_positive + false_negative
            class_scores.append(2 * true_positive / denominator if denominator else 0.0)
        macro_f1_values.append(sum(class_scores) / len(class_scores))
    return Metrics(
        attribute_accuracy=sum(field_accuracy) / len(field_accuracy),
        macro_f1=sum(macro_f1_values) / len(macro_f1_values),
        field_accuracy=field_accuracy,
    )


def mean_metrics(items: tuple[Metrics, ...]) -> Metrics:
    count = len(items)
    return Metrics(
        attribute_accuracy=sum(item.attribute_accuracy for item in items) / count,
        macro_f1=sum(item.macro_f1 for item in items) / count,
        field_accuracy=tuple(
            sum(item.field_accuracy[index] for item in items) / count
            for index in range(len(FIELD_NAMES))
        ),
    )


def image_features(model: CLIPModel, pixels: Tensor) -> Tensor:
    output = model.get_image_features(pixel_values=pixels)
    return output.pooler_output


def train_head(
    features: Tensor,
    labels: Tensor,
    training: tuple[int, ...],
    validation: tuple[int, ...],
    device: torch.device,
    epochs: int,
) -> tuple[Metrics, Metrics]:
    head = MultiHead(features.shape[1]).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.01, weight_decay=0.01)
    train_indices = torch.tensor(training, device=device)
    validation_indices = torch.tensor(validation, device=device)
    train_labels = labels.to(device)
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        outputs = head(features[train_indices])
        loss = sum(
            nn.functional.cross_entropy(output, train_labels[train_indices, index])
            for index, output in enumerate(outputs)
        )
        loss.backward()
        optimizer.step()
    head.eval()
    with torch.inference_mode():
        train_metrics = metric(head(features[train_indices]), train_labels[train_indices])
        validation_metrics = metric(
            head(features[validation_indices]), train_labels[validation_indices]
        )
    return train_metrics, validation_metrics


def train_partial_clip(
    pixels: Tensor,
    labels: Tensor,
    training: tuple[int, ...],
    validation: tuple[int, ...],
    checkpoint: str,
    device: torch.device,
    epochs: int,
) -> tuple[Metrics, Metrics]:
    model = CLIPModel.from_pretrained(checkpoint, local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.vision_model.encoder.layers[-2:].parameters():
        parameter.requires_grad = True
    model.visual_projection.weight.requires_grad = True
    head = MultiHead(model.visual_projection.out_features).to(device)
    visual_parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    optimizer = torch.optim.AdamW(
        [
            {"params": visual_parameters, "lr": 1e-5},
            {"params": head.parameters(), "lr": 1e-3},
        ],
        weight_decay=0.01,
    )
    train_indices = torch.tensor(training, device=device)
    validation_indices = torch.tensor(validation, device=device)
    train_labels = labels.to(device)
    pixels_device = pixels.to(device)
    for _ in range(epochs):
        optimizer.zero_grad(set_to_none=True)
        outputs = head(image_features(model, pixels_device[train_indices]))
        loss = sum(
            nn.functional.cross_entropy(output, train_labels[train_indices, index])
            for index, output in enumerate(outputs)
        )
        loss.backward()
        optimizer.step()
    model.eval()
    head.eval()
    with torch.inference_mode():
        train_outputs = head(image_features(model, pixels_device[train_indices]))
        validation_outputs = head(image_features(model, pixels_device[validation_indices]))
        train_metrics = metric(train_outputs, train_labels[train_indices])
        validation_metrics = metric(validation_outputs, train_labels[validation_indices])
    del model, head, optimizer, pixels_device
    if device.type == "cuda":
        torch.cuda.empty_cache()
    return train_metrics, validation_metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pa-root", type=Path, default=Path("experiments/data/cctv_proxy/pa100k"))
    parser.add_argument("--checkpoint", default="openai/clip-vit-base-patch32")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--folds", type=int, default=5)
    parser.add_argument("--head-epochs", type=int, default=120)
    parser.add_argument("--finetune-epochs", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = resolve_output_path(args.output)
    random.seed(17)
    torch.manual_seed(17)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    examples = read_examples(args.pa_root, args.limit)
    processor = CLIPProcessor.from_pretrained(args.checkpoint, local_files_only=True)
    pixels = load_pixels(examples, processor)
    labels = torch.tensor([example.labels for example in examples], dtype=torch.long)
    model = CLIPModel.from_pretrained(args.checkpoint, local_files_only=True).to(device).eval()
    with torch.inference_mode():
        features = image_features(model, pixels.to(device))
        features = features / features.norm(dim=1, keepdim=True).clamp_min(1e-6)
    del model
    fold_results: list[dict[str, object]] = []
    for fold_index, (training, validation) in enumerate(folds(len(examples), args.folds, 17)):
        head_train, head_validation = train_head(
            features, labels, training, validation, device, args.head_epochs
        )
        finetune_train, finetune_validation = train_partial_clip(
            pixels, labels, training, validation, args.checkpoint, device, args.finetune_epochs
        )
        fold_results.append(
            {
                "fold": fold_index,
                "train_count": len(training),
                "validation_count": len(validation),
                "linear_probe": {
                    "train": asdict(head_train),
                    "validation": asdict(head_validation),
                },
                "partial_clip_finetune": {
                    "train": asdict(finetune_train),
                    "validation": asdict(finetune_validation),
                },
            }
        )
    head_validation = mean_metrics(
        tuple(Metrics(**fold["linear_probe"]["validation"]) for fold in fold_results)
    )
    finetune_validation = mean_metrics(
        tuple(Metrics(**fold["partial_clip_finetune"]["validation"]) for fold in fold_results)
    )
    result = {
        "status": "valid",
        "dataset": "PA-100K local proxy subset",
        "examples": len(examples),
        "folds": args.folds,
        "split": "deterministic image-level 5-fold; no identity/track IDs are available",
        "checkpoint": args.checkpoint,
        "device": str(device),
        "provenance": {
            "seed": 17,
            "head_epochs": args.head_epochs,
            "finetune_epochs": args.finetune_epochs,
            "python": platform.python_version(),
            "torch": torch.__version__,
            "transformers": transformers.__version__,
            "gpu": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
            "data_manifest_sha256": sha256_file(args.pa_root / "manifest.jsonl"),
            "local_files_only": True,
        },
        "fields": {field: list(FIELD_CLASSES[field]) for field in FIELD_NAMES},
        "ceiling_note": (
            "This is the best observed proxy result among the tested recipes. Gold-label "
            "supervised transfer is an upper-bound proxy for response-level distillation; "
            "it is not a real CCTV identity ceiling."
        ),
        "linear_probe_validation": asdict(head_validation),
        "partial_clip_finetune_validation": asdict(finetune_validation),
        "folds_detail": fold_results,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(output),
                "examples": len(examples),
                "device": str(device),
                "linear_probe": asdict(head_validation),
                "partial_clip_finetune": asdict(finetune_validation),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
