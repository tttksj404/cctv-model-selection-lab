from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np


@dataclass(frozen=True, slots=True)
class AttributeSpec:
    label_name: str
    prompts: tuple[tuple[str, str], ...]


ATTRIBUTE_SPECS = {
    "PETA": (
        AttributeSpec(
            label_name="hairLong",
            prompts=(
                ("a person with long hair", "a person with short hair"),
                (
                    "a pedestrian with long hair extending below the ears",
                    "a pedestrian with short hair above the ears",
                ),
                ("long hairstyle", "short hairstyle"),
            ),
        ),
        AttributeSpec(
            label_name="accessorySunglasses",
            prompts=(
                ("a face wearing sunglasses", "a face without sunglasses"),
                (
                    "a person with dark sunglasses covering the eyes",
                    "a person with uncovered eyes and no glasses",
                ),
            ),
        ),
    ),
    "PA100k": (
        AttributeSpec(
            label_name="Glasses",
            prompts=(
                ("a face wearing eyeglasses", "a face without eyeglasses"),
                (
                    "a person with visible eyeglass frames",
                    "a person with bare eyes and no glasses",
                ),
            ),
        ),
        AttributeSpec(
            label_name="Hat",
            prompts=(
                ("a person wearing a hat", "a person with no hat"),
                (
                    "a pedestrian with visible headwear",
                    "a bareheaded pedestrian without headwear",
                ),
            ),
        ),
    ),
}


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=("PETA", "PA100k"), required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--checkpoint", default="openai/clip-vit-large-patch14")
    parser.add_argument(
        "--revision",
        default="32bd64288804d66eefd0ccbe215aa642df71cc41",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=8)
    return parser.parse_args(argv)


def _indices(partition: Any, split: str) -> np.ndarray:
    values = partition[split]
    if isinstance(values, list):
        values = values[0]
    return np.asarray(values, dtype=np.int64)


def _metrics(
    labels: np.ndarray,
    scores: np.ndarray,
    threshold: float,
) -> dict[str, float]:
    truth = labels > 0.5
    prediction = scores >= threshold
    true_positive = int(np.logical_and(prediction, truth).sum())
    true_negative = int(np.logical_and(~prediction, ~truth).sum())
    false_positive = int(np.logical_and(prediction, ~truth).sum())
    false_negative = int(np.logical_and(~prediction, truth).sum())

    def divide(numerator: int, denominator: int) -> float:
        return 0.0 if denominator == 0 else numerator / denominator

    recall = divide(true_positive, true_positive + false_negative)
    specificity = divide(true_negative, true_negative + false_positive)
    precision = divide(true_positive, true_positive + false_positive)
    f1 = divide(2 * true_positive, 2 * true_positive + false_positive + false_negative)
    return {
        "accuracy": divide(true_positive + true_negative, len(labels)),
        "meanAccuracy": (recall + specificity) / 2,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "positiveRate": float(truth.mean()),
        "predictedPositiveRate": float(prediction.mean()),
    }


def _calibrate(
    labels: np.ndarray,
    scores: np.ndarray,
) -> tuple[float, dict[str, float]]:
    best_threshold = 0.5
    best_metrics = _metrics(labels, scores, best_threshold)
    for threshold in np.linspace(0.05, 0.95, 181):
        candidate = _metrics(labels, scores, float(threshold))
        candidate_key = (candidate["meanAccuracy"], candidate["f1"])
        best_key = (best_metrics["meanAccuracy"], best_metrics["f1"])
        if candidate_key > best_key:
            best_threshold = float(threshold)
            best_metrics = candidate
    return best_threshold, best_metrics


def _checkpoint_digest(checkpoint: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(checkpoint.rglob("*")):
        if path.is_file() and not path.is_symlink():
            digest.update(path.relative_to(checkpoint).as_posix().encode())
            digest.update(str(path.stat().st_size).encode())
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    import torch
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset
    from transformers import CLIPModel, CLIPProcessor

    with (args.dataset_dir / "pad.pkl").open("rb") as handle:
        dataset_info = pickle.load(handle)
    image_names = tuple(str(value) for value in dataset_info.image_name)
    label_names = tuple(str(value) for value in dataset_info.attr_name)
    labels = np.asarray(dataset_info.label, dtype=np.float32)
    specs = ATTRIBUTE_SPECS[args.dataset]
    label_indices = {
        spec.label_name: label_names.index(spec.label_name) for spec in specs
    }

    class PersonDataset(Dataset[tuple[Any, Any]]):
        def __init__(self, split: str) -> None:
            self.indices = _indices(dataset_info.partition, split)

        def __len__(self) -> int:
            return len(self.indices)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            source_index = int(self.indices[index])
            with Image.open(args.image_root / image_names[source_index]) as source:
                image = source.convert("RGB")
            selected_labels = np.asarray(
                [labels[source_index, label_indices[spec.label_name]] for spec in specs],
                dtype=np.float32,
            )
            return image, selected_labels

    processor = CLIPProcessor.from_pretrained(
        args.checkpoint,
        revision=args.revision,
        local_files_only=True,
        use_fast=False,
    )
    device = torch.device("cuda")
    model = (
        CLIPModel.from_pretrained(
            args.checkpoint,
            revision=args.revision,
            dtype=torch.float16,
            local_files_only=True,
            use_safetensors=True,
        )
        .to(device)
        .eval()
    )
    prompt_pairs = [
        pair
        for spec in specs
        for pair in spec.prompts
    ]
    flat_prompts = [prompt for pair in prompt_pairs for prompt in pair]
    text_inputs = processor(text=flat_prompts, return_tensors="pt", padding=True)
    text_inputs = {name: value.to(device) for name, value in text_inputs.items()}
    with torch.inference_mode():
        text_features = model.get_text_features(**text_inputs).pooler_output
        text_features = torch.nn.functional.normalize(text_features, dim=-1)

    def collate(batch: list[tuple[Any, Any]]) -> tuple[list[Any], np.ndarray]:
        return [row[0] for row in batch], np.stack([row[1] for row in batch])

    def infer(split: str) -> tuple[np.ndarray, dict[str, np.ndarray]]:
        loader = DataLoader(
            PersonDataset(split),
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=True,
            collate_fn=collate,
        )
        label_batches: list[np.ndarray] = []
        score_batches: dict[str, list[np.ndarray]] = {
            f"{region}:{pair_index}": []
            for region in ("full", "head")
            for pair_index in range(len(prompt_pairs))
        }
        for images, batch_labels in loader:
            head_images = []
            for image in images:
                width, height = image.size
                head_images.append(
                    image.crop(
                        (
                            round(width * 0.10),
                            0,
                            max(round(width * 0.90), 1),
                            max(round(height * 0.45), 1),
                        )
                    )
                )
            label_batches.append(batch_labels)
            for region, region_images in (("full", images), ("head", head_images)):
                image_inputs = processor(images=region_images, return_tensors="pt")
                pixel_values = image_inputs["pixel_values"].to(
                    device,
                    dtype=model.dtype,
                )
                with torch.inference_mode():
                    image_features = model.get_image_features(
                        pixel_values=pixel_values
                    ).pooler_output
                    image_features = torch.nn.functional.normalize(
                        image_features,
                        dim=-1,
                    )
                    logits = model.logit_scale.exp().clamp(max=100.0) * (
                        image_features @ text_features.T
                    )
                for pair_index in range(len(prompt_pairs)):
                    pair_logits = logits[:, pair_index * 2 : pair_index * 2 + 2]
                    probabilities = torch.softmax(pair_logits.float(), dim=1)[:, 0]
                    score_batches[f"{region}:{pair_index}"].append(
                        probabilities.cpu().numpy()
                    )
        return (
            np.concatenate(label_batches),
            {
                key: np.concatenate(value_batches)
                for key, value_batches in score_batches.items()
            },
        )

    validation_labels, validation_scores = infer("val")
    test_labels, test_scores = infer("test")
    results = []
    pair_offset = 0
    for attribute_index, spec in enumerate(specs):
        candidates = []
        for local_pair_index, pair in enumerate(spec.prompts):
            pair_index = pair_offset + local_pair_index
            for region in ("full", "head"):
                score_key = f"{region}:{pair_index}"
                threshold, validation_metrics = _calibrate(
                    validation_labels[:, attribute_index],
                    validation_scores[score_key],
                )
                candidates.append(
                    {
                        "region": region,
                        "positivePrompt": pair[0],
                        "negativePrompt": pair[1],
                        "scoreKey": score_key,
                        "threshold": threshold,
                        "validationMetrics": validation_metrics,
                    }
                )
        selected = max(
            candidates,
            key=lambda row: (
                row["validationMetrics"]["meanAccuracy"],
                row["validationMetrics"]["f1"],
            ),
        )
        selected["testMetrics"] = _metrics(
            test_labels[:, attribute_index],
            test_scores[str(selected["scoreKey"])],
            float(selected["threshold"]),
        )
        results.append(
            {
                "attribute": spec.label_name,
                "selected": selected,
                "validationCandidates": candidates,
            }
        )
        pair_offset += len(spec.prompts)

    snapshot_root = (
        Path.home()
        / ".cache"
        / "huggingface"
        / "hub"
        / f"models--{args.checkpoint.replace('/', '--')}"
        / "snapshots"
        / args.revision
    )
    payload = {
        "schemaVersion": "clip-fine-attribute-heldout-v1",
        "dataset": args.dataset,
        "checkpoint": args.checkpoint,
        "revision": args.revision,
        "checkpointTreeDigest": _checkpoint_digest(snapshot_root),
        "selectionProtocol": (
            "prompt, region, and threshold selected on validation meanAccuracy; "
            "reported once on untouched test split"
        ),
        "validationCount": len(validation_labels),
        "testCount": len(test_labels),
        "attributes": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
