from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import random
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
from evaluate_clip_head_attributes_gpu import (
    ATTRIBUTE_SPECS,
    _calibrate,
    _checkpoint_digest,
    _indices,
    _metrics,
)


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
    parser.add_argument("--weights-output", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--num-workers", type=int, default=8)
    parser.add_argument("--epochs", type=int, default=80)
    parser.add_argument("--max-train-samples", type=int)
    parser.add_argument("--seed", type=int, default=20260731)
    return parser.parse_args(argv)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    import torch
    from PIL import Image
    from torch.utils.data import DataLoader, Dataset, TensorDataset
    from transformers import CLIPModel, CLIPProcessor

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.use_deterministic_algorithms(True, warn_only=True)

    with (args.dataset_dir / "pad.pkl").open("rb") as handle:
        dataset_info = pickle.load(handle)
    image_names = tuple(str(value) for value in dataset_info.image_name)
    label_names = tuple(str(value) for value in dataset_info.attr_name)
    labels = np.asarray(dataset_info.label, dtype=np.float32)
    specs = ATTRIBUTE_SPECS[args.dataset]
    label_indices = tuple(label_names.index(spec.label_name) for spec in specs)

    class PersonDataset(Dataset[tuple[Any, Any]]):
        def __init__(self, split: str) -> None:
            self.indices = _indices(dataset_info.partition, split)
            if (
                split == "train"
                and args.max_train_samples is not None
                and len(self.indices) > args.max_train_samples
            ):
                generator = np.random.default_rng(args.seed)
                self.indices = np.sort(
                    generator.choice(
                        self.indices,
                        size=args.max_train_samples,
                        replace=False,
                    )
                )

        def __len__(self) -> int:
            return len(self.indices)

        def __getitem__(self, index: int) -> tuple[Any, Any]:
            source_index = int(self.indices[index])
            with Image.open(args.image_root / image_names[source_index]) as source:
                image = source.convert("RGB")
            selected_labels = labels[source_index, label_indices].copy()
            return image, selected_labels

    def collate(batch: list[tuple[Any, Any]]) -> tuple[list[Any], np.ndarray]:
        return [row[0] for row in batch], np.stack([row[1] for row in batch])

    processor = CLIPProcessor.from_pretrained(
        args.checkpoint,
        revision=args.revision,
        local_files_only=True,
        use_fast=False,
    )
    device = torch.device("cuda")
    clip_model = (
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

    def extract(split: str) -> tuple[torch.Tensor, torch.Tensor]:
        loader = DataLoader(
            PersonDataset(split),
            batch_size=args.batch_size,
            shuffle=False,
            num_workers=args.num_workers,
            pin_memory=True,
            collate_fn=collate,
        )
        feature_batches: list[torch.Tensor] = []
        label_batches: list[torch.Tensor] = []
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
            region_features = []
            for region_images in (images, head_images):
                image_inputs = processor(images=region_images, return_tensors="pt")
                pixel_values = image_inputs["pixel_values"].to(
                    device,
                    dtype=clip_model.dtype,
                )
                with torch.inference_mode():
                    features = clip_model.get_image_features(
                        pixel_values=pixel_values
                    ).pooler_output
                    features = torch.nn.functional.normalize(features, dim=-1)
                region_features.append(features.float().cpu())
            feature_batches.append(torch.cat(region_features, dim=1))
            label_batches.append(torch.from_numpy(batch_labels))
        return torch.cat(feature_batches), torch.cat(label_batches)

    split_features = {
        split: extract(split)
        for split in ("train", "val", "test")
    }
    clip_model.to("cpu")
    torch.cuda.empty_cache()

    train_features, train_labels = split_features["train"]
    input_dim = train_features.shape[1]
    output_dim = train_labels.shape[1]
    positive = train_labels.sum(dim=0)
    negative = len(train_labels) - positive
    positive_weight = (negative / positive.clamp_min(1.0)).to(device)

    architectures: dict[str, Any] = {
        "linear": lambda: torch.nn.Linear(input_dim, output_dim),
        "mlp": lambda: torch.nn.Sequential(
            torch.nn.Linear(input_dim, 512),
            torch.nn.GELU(),
            torch.nn.Dropout(0.15),
            torch.nn.Linear(512, output_dim),
        ),
    }
    validation_candidates = []
    trained_states: dict[str, dict[str, torch.Tensor]] = {}
    for architecture_name, factory in architectures.items():
        torch.manual_seed(args.seed)
        model = factory().to(device)
        optimizer = torch.optim.AdamW(model.parameters(), lr=3e-4, weight_decay=1e-3)
        loss_function = torch.nn.BCEWithLogitsLoss(pos_weight=positive_weight)
        generator = torch.Generator().manual_seed(args.seed)
        loader = DataLoader(
            TensorDataset(train_features, train_labels),
            batch_size=1024,
            shuffle=True,
            generator=generator,
        )
        best_state: dict[str, torch.Tensor] | None = None
        best_validation_ma = -1.0
        best_thresholds: list[float] = []
        best_validation_metrics: list[dict[str, float]] = []
        for _epoch in range(args.epochs):
            model.train()
            for features, targets in loader:
                optimizer.zero_grad(set_to_none=True)
                logits = model(features.to(device))
                loss = loss_function(logits, targets.to(device))
                loss.backward()
                optimizer.step()

            model.eval()
            validation_features, validation_labels = split_features["val"]
            with torch.inference_mode():
                validation_scores = torch.sigmoid(
                    model(validation_features.to(device))
                ).cpu().numpy()
            thresholds = []
            validation_metrics = []
            for attribute_index in range(output_dim):
                threshold, metrics = _calibrate(
                    validation_labels[:, attribute_index].numpy(),
                    validation_scores[:, attribute_index],
                )
                thresholds.append(threshold)
                validation_metrics.append(metrics)
            validation_ma = float(
                np.mean([metrics["meanAccuracy"] for metrics in validation_metrics])
            )
            if validation_ma > best_validation_ma:
                best_validation_ma = validation_ma
                best_thresholds = thresholds
                best_validation_metrics = validation_metrics
                best_state = {
                    name: value.detach().cpu().clone()
                    for name, value in model.state_dict().items()
                }
        if best_state is None:
            raise RuntimeError("attribute head training did not produce a checkpoint")
        trained_states[architecture_name] = best_state
        validation_candidates.append(
            {
                "architecture": architecture_name,
                "meanAccuracy": best_validation_ma,
                "thresholds": best_thresholds,
                "attributeMetrics": best_validation_metrics,
            }
        )

    selected = max(
        validation_candidates,
        key=lambda row: float(row["meanAccuracy"]),
    )
    selected_name = str(selected["architecture"])
    selected_model = architectures[selected_name]().to(device)
    selected_model.load_state_dict(trained_states[selected_name])
    selected_model.eval()
    test_features, test_labels = split_features["test"]
    with torch.inference_mode():
        test_scores = torch.sigmoid(
            selected_model(test_features.to(device))
        ).cpu().numpy()
    test_metrics = []
    for attribute_index, spec in enumerate(specs):
        metrics = _metrics(
            test_labels[:, attribute_index].numpy(),
            test_scores[:, attribute_index],
            float(selected["thresholds"][attribute_index]),
        )
        test_metrics.append(
            {
                "attribute": spec.label_name,
                "threshold": selected["thresholds"][attribute_index],
                "metrics": metrics,
            }
        )

    args.weights_output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(
        {
            "schemaVersion": "clip-fine-attribute-head-v1",
            "dataset": args.dataset,
            "checkpoint": args.checkpoint,
            "revision": args.revision,
            "architecture": selected_name,
            "inputRegions": ["full", "head"],
            "attributes": [spec.label_name for spec in specs],
            "thresholds": selected["thresholds"],
            "stateDict": trained_states[selected_name],
        },
        args.weights_output,
    )
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
        "schemaVersion": "clip-fine-attribute-head-heldout-v1",
        "dataset": args.dataset,
        "checkpoint": args.checkpoint,
        "revision": args.revision,
        "checkpointTreeDigest": _checkpoint_digest(snapshot_root),
        "splitCounts": {
            split: len(split_features[split][1])
            for split in ("train", "val", "test")
        },
        "selectionProtocol": (
            "architecture, epoch, and per-attribute threshold selected only on "
            "validation meanAccuracy; test reported once after selection"
        ),
        "validationCandidates": validation_candidates,
        "selectedArchitecture": selected_name,
        "testAttributes": test_metrics,
        "testMeanAccuracy": float(
            np.mean([row["metrics"]["meanAccuracy"] for row in test_metrics])
        ),
        "weights": {
            "path": str(args.weights_output),
            "sha256": _sha256(args.weights_output),
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
