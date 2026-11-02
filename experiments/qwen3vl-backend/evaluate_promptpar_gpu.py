from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np

PETA_LEGACY_SHORT_PROMPTS = (
    "head hat",
    "head muffler",
    "head nothing",
    "head sunglasses",
    "head long hair",
    "upper casual",
    "upper formal",
    "upper jacket",
    "upper logo",
    "upper plaid",
    "upper short sleeve",
    "upper thin stripes",
    "upper t-shirt",
    "upper other",
    "upper v-neck",
    "lower Casual",
    "lower Formal",
    "lower Jeans",
    "lower Shorts",
    "lower Short Skirt",
    "lower Trousers",
    "shoes Leather",
    "shoes Sandals",
    "shoes other",
    "shoes sneaker",
    "attach Backpack",
    "attach Other",
    "attach messenger bag",
    "attach nothing",
    "attach plastic bags",
    "age less 30",
    "age 30 45",
    "age 45 60",
    "age over 60",
    "male",
)

PA100K_LEGACY_SHORT_PROMPTS = (
    "female",
    "age over 60",
    "age 18 to 60",
    "age less 18",
    "front",
    "side",
    "back",
    "hat",
    "glasses",
    "hand bag",
    "shoulder bag",
    "backpack",
    "hold objects in front",
    "short sleeve",
    "long sleeve",
    "upper stride",
    "upper logo",
    "upper plaid",
    "upper splice",
    "lower stripe",
    "lower pattern",
    "long coat",
    "trousers",
    "shorts",
    "skirt and dress",
    "boots",
)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--openpar-root", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--pretrained-vit", type=Path, required=True)
    parser.add_argument("--dataset", choices=("PETA", "PA100k"), required=True)
    parser.add_argument("--dataset-dir", type=Path, required=True)
    parser.add_argument(
        "--prompt-style",
        choices=("official-pad", "legacy-short"),
        default="official-pad",
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=8)
    return parser.parse_args(argv)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _indices(partition: Any, split: str) -> np.ndarray:
    values = partition[split]
    if isinstance(values, list):
        values = values[0]
    return np.asarray(values, dtype=np.int64)


def _binary_metrics(
    labels: np.ndarray,
    probabilities: np.ndarray,
    thresholds: np.ndarray,
) -> dict[str, Any]:
    predictions = probabilities >= thresholds.reshape(1, -1)
    truth = labels > 0.5
    true_positive = np.logical_and(predictions, truth).sum(axis=0)
    true_negative = np.logical_and(~predictions, ~truth).sum(axis=0)
    false_positive = np.logical_and(predictions, ~truth).sum(axis=0)
    false_negative = np.logical_and(~predictions, truth).sum(axis=0)

    positive_recall = np.divide(
        true_positive,
        true_positive + false_negative,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=(true_positive + false_negative) > 0,
    )
    negative_recall = np.divide(
        true_negative,
        true_negative + false_positive,
        out=np.zeros_like(true_negative, dtype=np.float64),
        where=(true_negative + false_positive) > 0,
    )
    precision = np.divide(
        true_positive,
        true_positive + false_positive,
        out=np.zeros_like(true_positive, dtype=np.float64),
        where=(true_positive + false_positive) > 0,
    )
    recall = positive_recall
    label_f1 = np.divide(
        2 * precision * recall,
        precision + recall,
        out=np.zeros_like(precision, dtype=np.float64),
        where=(precision + recall) > 0,
    )

    instance_intersection = np.logical_and(predictions, truth).sum(axis=1)
    instance_union = np.logical_or(predictions, truth).sum(axis=1)
    predicted_count = predictions.sum(axis=1)
    truth_count = truth.sum(axis=1)
    instance_accuracy = np.divide(
        instance_intersection,
        instance_union,
        out=np.zeros_like(instance_intersection, dtype=np.float64),
        where=instance_union > 0,
    )
    instance_precision = np.divide(
        instance_intersection,
        predicted_count,
        out=np.zeros_like(instance_intersection, dtype=np.float64),
        where=predicted_count > 0,
    )
    instance_recall = np.divide(
        instance_intersection,
        truth_count,
        out=np.zeros_like(instance_intersection, dtype=np.float64),
        where=truth_count > 0,
    )
    instance_f1 = np.divide(
        2 * instance_precision * instance_recall,
        instance_precision + instance_recall,
        out=np.zeros_like(instance_precision, dtype=np.float64),
        where=(instance_precision + instance_recall) > 0,
    )
    label_ma = (positive_recall + negative_recall) / 2
    return {
        "meanAccuracy": float(label_ma.mean()),
        "instanceAccuracy": float(instance_accuracy.mean()),
        "instancePrecision": float(instance_precision.mean()),
        "instanceRecall": float(instance_recall.mean()),
        "instanceF1": float(instance_f1.mean()),
        "labelMacroF1": float(label_f1.mean()),
        "labelPositiveRecall": positive_recall.tolist(),
        "labelNegativeRecall": negative_recall.tolist(),
        "labelPrecision": precision.tolist(),
        "labelF1": label_f1.tolist(),
        "labelMeanAccuracy": label_ma.tolist(),
    }


def _calibrate_thresholds(
    labels: np.ndarray,
    probabilities: np.ndarray,
) -> np.ndarray:
    grid = np.linspace(0.05, 0.95, 91, dtype=np.float64)
    thresholds = np.full(labels.shape[1], 0.5, dtype=np.float64)
    for attribute_index in range(labels.shape[1]):
        truth = labels[:, attribute_index] > 0.5
        best_score = -1.0
        best_threshold = 0.5
        for threshold in grid:
            prediction = probabilities[:, attribute_index] >= threshold
            true_positive = int(np.logical_and(prediction, truth).sum())
            false_positive = int(np.logical_and(prediction, ~truth).sum())
            false_negative = int(np.logical_and(~prediction, truth).sum())
            denominator = 2 * true_positive + false_positive + false_negative
            score = 0.0 if denominator == 0 else 2 * true_positive / denominator
            if score > best_score:
                best_score = score
                best_threshold = float(threshold)
        thresholds[attribute_index] = best_threshold
    return thresholds


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    sys.path.insert(0, str(args.openpar_root))
    sys.argv = [
        "evaluate_promptpar_gpu.py",
        args.dataset,
        "--checkpoint",
        "--dir",
        str(args.checkpoint),
        "--use_div",
        "--use_vismask",
        "--vis_prompt",
        "50",
        "--use_GL",
        "--use_textprompt",
        "--use_mm_former",
    ]

    import torch
    from clip.model import build_model
    from models.base_block import TransformerClassifier
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset
    from torchvision import transforms

    with (args.dataset_dir / "pad.pkl").open("rb") as handle:
        dataset_info = pickle.load(handle)
    official_prompts = tuple(str(value) for value in dataset_info.attributes)
    if args.prompt_style == "legacy-short":
        attributes = (
            PETA_LEGACY_SHORT_PROMPTS
            if args.dataset == "PETA"
            else PA100K_LEGACY_SHORT_PROMPTS
        )
    else:
        attributes = official_prompts
    labels = np.asarray(dataset_info.label, dtype=np.float32)
    if len(attributes) != labels.shape[1]:
        raise ValueError("prompt count does not match dataset labels")
    label_names = tuple(str(value) for value in dataset_info.attr_name)
    image_names = tuple(str(value) for value in dataset_info.image_name)
    image_root = Path(dataset_info.root)
    normalize = transforms.Compose(
        (
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(mean=(0.5, 0.5, 0.5), std=(0.5, 0.5, 0.5)),
        )
    )

    class AttributeDataset(Dataset[tuple[Any, Any]]):
        def __init__(self, split: str) -> None:
            self.indices = _indices(dataset_info.partition, split)

        def __len__(self) -> int:
            return len(self.indices)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            source_index = int(self.indices[index])
            with Image.open(image_root / image_names[source_index]) as source:
                image = source.convert("RGB")
            return normalize(image), labels[source_index]

    checkpoint = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
    clip_model = build_model(checkpoint["ViT_model"])
    model = TransformerClassifier(
        clip_model,
        len(attributes),
        attributes,
        pretrain_path=str(args.pretrained_vit),
    )
    state_dict = {
        key.replace("vis_embed.", "visual_embed."): value
        for key, value in checkpoint["model_state_dict"].items()
    }
    load_result = model.load_state_dict(state_dict, strict=False)
    disallowed_unexpected = [
        key for key in load_result.unexpected_keys if not key.startswith("vit.")
    ]
    if load_result.missing_keys or disallowed_unexpected:
        raise RuntimeError(
            "checkpoint integrity failure: "
            f"missing={load_result.missing_keys}, unexpected={disallowed_unexpected}"
        )
    device = torch.device("cuda")
    model = model.to(device).eval()
    clip_model = clip_model.to(device).eval()

    def infer(split: str) -> tuple[np.ndarray, np.ndarray]:
        loader = DataLoader(
            AttributeDataset(split),
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=True,
        )
        probability_batches: list[np.ndarray] = []
        label_batches: list[np.ndarray] = []
        with torch.inference_mode():
            for images, batch_labels in loader:
                logits, _ = model(
                    images.to(device, non_blocking=True),
                    clip_model=clip_model,
                )
                probability_batches.append(torch.sigmoid(logits).cpu().numpy())
                label_batches.append(batch_labels.numpy())
        return np.concatenate(label_batches), np.concatenate(probability_batches)

    validation_labels, validation_probabilities = infer("val")
    test_labels, test_probabilities = infer("test")
    official_thresholds = np.full(len(attributes), 0.45, dtype=np.float64)
    calibrated_thresholds = _calibrate_thresholds(
        validation_labels,
        validation_probabilities,
    )
    official_metrics = _binary_metrics(
        test_labels,
        test_probabilities,
        official_thresholds,
    )
    calibrated_metrics = _binary_metrics(
        test_labels,
        test_probabilities,
        calibrated_thresholds,
    )
    for metrics in (official_metrics, calibrated_metrics):
        metrics["perAttribute"] = [
            {
                "attribute": attribute,
                "positiveRecall": metrics["labelPositiveRecall"][index],
                "negativeRecall": metrics["labelNegativeRecall"][index],
                "precision": metrics["labelPrecision"][index],
                "f1": metrics["labelF1"][index],
                "meanAccuracy": metrics["labelMeanAccuracy"][index],
            }
            for index, attribute in enumerate(label_names)
        ]
        for temporary_key in (
            "labelPositiveRecall",
            "labelNegativeRecall",
            "labelPrecision",
            "labelF1",
            "labelMeanAccuracy",
        ):
            del metrics[temporary_key]

    payload = {
        "schemaVersion": "promptpar-heldout-evaluation-v1",
        "dataset": args.dataset,
        "promptStyle": args.prompt_style,
        "prompts": attributes,
        "checkpoint": str(args.checkpoint),
        "checkpointSha256": sha256_file(args.checkpoint),
        "preprocessing": "resize-224-normalize-0.5",
        "validationCount": len(validation_labels),
        "testCount": len(test_labels),
        "loadIntegrity": {
            "missingKeys": [],
            "disallowedUnexpectedKeys": [],
            "ignoredPretrainedVitKeyCount": len(load_result.unexpected_keys),
        },
        "officialThreshold": {
            "thresholds": official_thresholds.tolist(),
            "metrics": official_metrics,
        },
        "validationCalibratedThreshold": {
            "thresholds": calibrated_thresholds.tolist(),
            "metrics": calibrated_metrics,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
