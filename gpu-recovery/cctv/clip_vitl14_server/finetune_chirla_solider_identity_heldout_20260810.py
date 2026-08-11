from __future__ import annotations

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

"""Identity-heldout SOLIDER fine-tuning for the CHIRLA proxy benchmark.

The sealed evaluation manifest is never loaded here.  Hyperparameters and the
best epoch are selected only from the fit/validation manifest; the output
checkpoint omits the temporary training classifier so the normal inference
benchmark can load it with its production model shape.
"""

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict, cast

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F
from torchvision.transforms import (
    ColorJitter,
    Compose,
    Pad,
    RandomCrop,
    RandomErasing,
    RandomGrayscale,
    RandomHorizontalFlip,
    ToTensor,
)

from scripts.benchmark_chirla_reid import ImageEncoder
from scripts.benchmark_clipreid_support import validate_track_protocol
from scripts.prid2011_track_metrics import pool_tracks


class ManifestRow(TypedDict):
    localPath: str
    sha256: str
    identityGroupId: str
    cameraId: str
    trackId: str
    sequenceId: str
    benchmarkRole: str
    split: str


class ExperimentError(RuntimeError):
    pass


def required_text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ExperimentError(f"manifest field {key!r} must be non-empty text")
    return value


def load_manifest(root: Path, manifest: Path) -> list[ManifestRow]:
    resolved_root = root.resolve()
    rows: list[ManifestRow] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw = json.loads(line)
        if not isinstance(raw, dict):
            raise ExperimentError("manifest rows must be JSON objects")
        row: ManifestRow = {
            "localPath": required_text(raw, "localPath"),
            "sha256": required_text(raw, "sha256"),
            "identityGroupId": required_text(raw, "identityGroupId"),
            "cameraId": required_text(raw, "cameraId"),
            "trackId": required_text(raw, "trackId"),
            "sequenceId": required_text(raw, "sequenceId"),
            "benchmarkRole": required_text(raw, "benchmarkRole"),
            "split": required_text(raw, "split"),
        }
        image = (resolved_root / row["localPath"]).resolve()
        if not image.is_relative_to(resolved_root) or not image.is_file():
            raise FileNotFoundError(image)
        if hashlib.sha256(image.read_bytes()).hexdigest() != row["sha256"]:
            raise ExperimentError(f"manifest sha256 mismatch: {image}")
        rows.append(row)
    validate_track_protocol(rows)
    if not any(row["split"] == "train" for row in rows):
        raise ExperimentError("fit split is empty")
    if not any(row["split"] == "validation" for row in rows):
        raise ExperimentError("validation split is empty")
    return rows


class BalancedIdentitySampler:
    def __init__(
        self,
        rows: Sequence[ManifestRow],
        *,
        identities_per_batch: int,
        images_per_identity: int,
        seed: int,
    ) -> None:
        grouped: dict[str, dict[str, list[ManifestRow]]] = defaultdict(lambda: defaultdict(list))
        for row in rows:
            grouped[row["identityGroupId"]][row["cameraId"]].append(row)
        self.grouped = {
            identity: dict(cameras)
            for identity, cameras in grouped.items()
            if len(cameras) >= 2
        }
        self.identities = sorted(self.grouped)
        if len(self.identities) < identities_per_batch:
            raise ExperimentError(
                f"only {len(self.identities)} fit identities have two cameras; "
                f"cannot build batch with {identities_per_batch} identities"
            )
        self.identity_index = {identity: index for index, identity in enumerate(self.identities)}
        self.identities_per_batch = identities_per_batch
        self.images_per_identity = images_per_identity
        self.rng = random.Random(seed)

    def sample(self) -> tuple[list[ManifestRow], list[int]]:
        selected = self.rng.sample(self.identities, self.identities_per_batch)
        rows: list[ManifestRow] = []
        labels: list[int] = []
        for identity in selected:
            by_camera = self.grouped[identity]
            cameras = sorted(by_camera)
            picked = [self.rng.choice(by_camera[cameras[0]]), self.rng.choice(by_camera[cameras[1]])]
            all_rows = [row for camera_rows in by_camera.values() for row in camera_rows]
            while len(picked) < self.images_per_identity:
                picked.append(self.rng.choice(all_rows))
            rows.extend(picked)
            labels.extend([self.identity_index[identity]] * len(picked))
        return rows, labels


class ArcMarginHead(nn.Module):
    def __init__(self, feature_dim: int, classes: int, *, scale: float, margin: float) -> None:
        super().__init__()
        self.scale = scale
        self.margin = margin
        self.weight = nn.Parameter(torch.empty(classes, feature_dim))
        nn.init.xavier_uniform_(self.weight)
        self.cos_margin = math.cos(margin)
        self.sin_margin = math.sin(margin)
        self.threshold = math.cos(math.pi - margin)
        self.margin_adjustment = math.sin(math.pi - margin) * margin

    def forward(self, features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
        cosine = F.linear(F.normalize(features), F.normalize(self.weight))
        sine = torch.sqrt(torch.clamp(1.0 - cosine.square(), min=1e-7))
        angular = cosine * self.cos_margin - sine * self.sin_margin
        angular = torch.where(cosine > self.threshold, angular, cosine - self.margin_adjustment)
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(dtype=cosine.dtype)
        return self.scale * (one_hot * angular + (1.0 - one_hot) * cosine)


def batch_hard_triplet(features: torch.Tensor, labels: torch.Tensor, margin: float) -> torch.Tensor:
    normalized = F.normalize(features)
    distances = torch.cdist(normalized, normalized, p=2)
    same = labels[:, None].eq(labels[None, :])
    same.fill_diagonal_(False)
    different = ~labels[:, None].eq(labels[None, :])
    positive = distances.masked_fill(~same, float("-inf")).max(dim=1).values
    negative = distances.masked_fill(~different, float("inf")).min(dim=1).values
    valid = torch.isfinite(positive) & torch.isfinite(negative)
    if not bool(valid.any()):
        raise ExperimentError("batch-hard triplet found no valid positive/negative pair")
    return F.softplus(positive[valid] - negative[valid] + margin).mean()


def part_triplet(feature_map: torch.Tensor, labels: torch.Tensor, parts: int, margin: float) -> torch.Tensor:
    if feature_map.ndim != 4:
        raise ExperimentError("SOLIDER feature map is not BCHW")
    losses = [
        batch_hard_triplet(stripe.mean(dim=(2, 3)), labels, margin)
        for stripe in torch.tensor_split(feature_map, parts, dim=2)
        if stripe.shape[2] > 0
    ]
    return torch.stack(losses).mean()


def load_batch(root: Path, rows: Sequence[ManifestRow], transform: Compose, device: torch.device) -> torch.Tensor:
    images: list[torch.Tensor] = []
    for row in rows:
        with Image.open(root / row["localPath"]) as image:
            images.append(transform(image.convert("RGB")))
    return torch.stack(images).to(device, non_blocking=True)


def encode_rows(
    root: Path,
    rows: Sequence[ManifestRow],
    model: nn.Module,
    transform: Compose,
    device: torch.device,
    batch_size: int,
    tta: bool = False,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            inputs = load_batch(root, rows[start : start + batch_size], transform, device)
            output = model(inputs)
            if not isinstance(output, tuple) or not isinstance(output[0], torch.Tensor):
                raise ExperimentError("SOLIDER evaluation output is not a feature tuple")
            features = output[0]
            if tta:
                flipped = model(torch.flip(inputs, dims=(3,)))
                if not isinstance(flipped, tuple) or not isinstance(flipped[0], torch.Tensor):
                    raise ExperimentError("SOLIDER hflip output is not a feature tuple")
                features = F.normalize(features, dim=-1) + F.normalize(flipped[0], dim=-1)
            chunks.append(F.normalize(features, dim=-1).float().cpu().numpy())
    return np.concatenate(chunks, axis=0)


def strict_closed_set_metrics(rows: Sequence[ManifestRow], vectors: np.ndarray) -> dict[str, object]:
    tracks = pool_tracks(cast(list[dict[str, object]], list(rows)), vectors)
    gallery = [track for track in tracks if track.role == "gallery"]
    queries = [track for track in tracks if track.role == "query"]
    if not gallery or not queries:
        raise ExperimentError("validation requires gallery and query tracks")
    rank1 = 0
    recall5 = 0
    reciprocal: list[float] = []
    eligible = 0
    excluded = 0
    for query in queries:
        candidates = [
            track for track in gallery
            if track.camera != query.camera and track.split == query.split
            and track.track_id != query.track_id
            and track.camera != ""
            and track.identity
        ]
        by_identity: dict[str, list[np.ndarray]] = defaultdict(list)
        for candidate in candidates:
            by_identity[candidate.identity].append(candidate.vector)
        identity_vectors = {
            identity: F.normalize(torch.from_numpy(np.mean(values, axis=0)), dim=0).numpy()
            for identity, values in by_identity.items()
        }
        if query.identity not in identity_vectors or len(identity_vectors) < 2:
            excluded += 1
            continue
        eligible += 1
        ranked = sorted(
            identity_vectors,
            key=lambda identity: float(np.dot(query.vector, identity_vectors[identity])),
            reverse=True,
        )
        rank = ranked.index(query.identity) + 1
        rank1 += rank == 1
        recall5 += rank <= 5
        reciprocal.append(1.0 / rank)
    if not eligible:
        raise ExperimentError("strict validation has no eligible queries")
    return {
        "queryTracks": len(queries),
        "eligibleQueries": eligible,
        "strictExcludedQueries": excluded,
        "rank1": rank1 / eligible,
        "recallAt5": recall5 / eligible,
        "mrr": float(np.mean(reciprocal)),
    }


def validation_key(metrics: dict[str, object]) -> tuple[float, ...]:
    return (
        float(metrics["rank1"]),
        float(metrics["recallAt5"]),
        float(metrics["mrr"]),
        -float(metrics["strictExcludedQueries"]),
    )


def save_production_checkpoint(model: nn.Module, path: Path) -> str:
    state = {
        key: value.detach().cpu()
        for key, value in model.state_dict().items()
        if not key.startswith("classifier.")
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    torch.save(state, path)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--expected-checkpoint-sha256", required=True)
    parser.add_argument("--solider-root", type=Path, required=True)
    parser.add_argument("--solider-runtime-id", default="SOLIDER-REID-runtime-8c08e1c")
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--warmup-epochs", type=int, default=1)
    parser.add_argument("--steps-per-epoch", type=int, default=25)
    parser.add_argument("--identities-per-batch", type=int, default=8)
    parser.add_argument("--images-per-identity", type=int, default=4)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--backbone-lr", type=float, default=2e-6)
    parser.add_argument("--head-lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--arc-weight", type=float, default=1.0)
    parser.add_argument("--classifier-weight", type=float, default=0.20)
    parser.add_argument("--triplet-weight", type=float, default=1.0)
    parser.add_argument("--part-weight", type=float, default=0.20)
    parser.add_argument("--teacher-weight", type=float, default=1.0)
    parser.add_argument("--triplet-margin", type=float, default=0.20)
    parser.add_argument("--arc-margin", type=float, default=0.20)
    parser.add_argument("--arc-scale", type=float, default=32.0)
    parser.add_argument("--seed", type=int, default=20260810)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not torch.cuda.is_available() and args.device.startswith("cuda"):
        raise ExperimentError("CUDA is required for this experiment")
    actual_source_sha = hashlib.sha256(args.checkpoint.read_bytes()).hexdigest()
    if actual_source_sha != args.expected_checkpoint_sha256:
        raise ExperimentError("source SOLIDER checkpoint SHA-256 mismatch")
    runtime_source = args.solider_root / "model" / "make_model.py"
    if not runtime_source.is_file():
        raise ExperimentError(f"SOLIDER runtime source is missing: {runtime_source}")
    solider_runtime_sha = hashlib.sha256(runtime_source.read_bytes()).hexdigest()
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device(args.device)
    rows = load_manifest(args.root, args.manifest)
    train_rows = [row for row in rows if row["split"] == "train"]
    validation_rows = [row for row in rows if row["split"] == "validation"]
    sampler = BalancedIdentitySampler(
        train_rows,
        identities_per_batch=args.identities_per_batch,
        images_per_identity=args.images_per_identity,
        seed=args.seed,
    )
    train_identities = sampler.identities
    student_encoder = ImageEncoder(
        "solider-reid-swin-base-msmt17",
        device,
        checkpoint_override=str(args.checkpoint),
        solider_root=args.solider_root,
        tta="none",
    )
    teacher_encoder = ImageEncoder(
        "solider-reid-swin-base-msmt17",
        device,
        checkpoint_override=str(args.checkpoint),
        solider_root=args.solider_root,
        tta="none",
    )
    student = cast(nn.Module, student_encoder.model)
    teacher = cast(nn.Module, teacher_encoder.model).eval()
    for parameter in teacher.parameters():
        parameter.requires_grad_(False)
    for parameter in student.parameters():
        parameter.requires_grad_(False)
    feature_dim = 1024
    trainable_base: list[nn.Parameter] = []
    trainable_neck: list[nn.Parameter] = []
    for name, parameter in student.named_parameters():
        if name.startswith(("base.stages.3.", "base.norm", "base.layers.3.")):
            parameter.requires_grad_(True)
            trainable_base.append(parameter)
        elif name.startswith("bottleneck."):
            parameter.requires_grad_(True)
            trainable_neck.append(parameter)
    student.classifier = nn.Linear(feature_dim, len(train_identities), bias=False, device=device)
    trainable_neck.extend(student.classifier.parameters())
    arc_head = ArcMarginHead(
        feature_dim,
        len(train_identities),
        scale=args.arc_scale,
        margin=args.arc_margin,
    ).to(device)
    train_transform = cast(Compose, student_encoder.processor)
    resize_transform = train_transform.transforms[0]
    normalize_transform = train_transform.transforms[-1]
    train_transform = Compose([
        resize_transform,
        Pad(10),
        RandomCrop((384, 128)),
        RandomHorizontalFlip(),
        ColorJitter(brightness=0.25, contrast=0.25, saturation=0.20, hue=0.05),
        RandomGrayscale(p=0.05),
        ToTensor(),
        normalize_transform,
        RandomErasing(p=0.50, scale=(0.02, 0.25), ratio=(0.3, 3.3)),
    ])
    eval_transform = cast(Compose, student_encoder.processor)
    optimizer = torch.optim.AdamW([
        {"params": trainable_base, "lr": args.backbone_lr},
        {"params": trainable_neck, "lr": args.head_lr},
        {"params": arc_head.parameters(), "lr": args.head_lr},
    ], weight_decay=args.weight_decay)
    total_steps = max(1, args.epochs * args.steps_per_epoch)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=total_steps)
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)

    baseline_vectors = encode_rows(args.root, validation_rows, student, eval_transform, device, args.eval_batch_size)
    baseline = strict_closed_set_metrics(validation_rows, baseline_vectors)
    print(json.dumps({"epoch": 0, "validation": baseline}, sort_keys=True), flush=True)
    best_key = validation_key(baseline)
    best_epoch = 0
    best_validation = baseline
    save_production_checkpoint(student, args.output_checkpoint)
    history: list[dict[str, object]] = []
    for epoch in range(1, args.epochs + 1):
        backbone_enabled = epoch > args.warmup_epochs
        for parameter in trainable_base:
            parameter.requires_grad_(backbone_enabled)
        student.train()
        running: dict[str, float] = defaultdict(float)
        for _ in range(args.steps_per_epoch):
            batch_rows, label_rows = sampler.sample()
            inputs = load_batch(args.root, batch_rows, train_transform, device)
            labels = torch.tensor(label_rows, dtype=torch.long, device=device)
            optimizer.zero_grad(set_to_none=True)
            with torch.inference_mode():
                teacher_output = teacher(inputs)
                if not isinstance(teacher_output, tuple) or not isinstance(teacher_output[0], torch.Tensor):
                    raise ExperimentError("teacher output is invalid")
                teacher_features = teacher_output[0]
            with torch.autocast(device_type=device.type, dtype=torch.float16, enabled=device.type == "cuda"):
                output = student(inputs, label=labels)
                if (
                    not isinstance(output, tuple)
                    or len(output) < 3
                    or not isinstance(output[0], torch.Tensor)
                    or not isinstance(output[1], torch.Tensor)
                    or not isinstance(output[2], list)
                    or not isinstance(output[2][-1], torch.Tensor)
                ):
                    raise ExperimentError("student training output is invalid")
                classifier_loss = F.cross_entropy(output[0], labels)
                features = output[1]
                final_map = output[2][-1]
                arc_loss = F.cross_entropy(arc_head(features, labels), labels, label_smoothing=0.10)
                triplet_loss = batch_hard_triplet(features, labels, args.triplet_margin)
                local_loss = part_triplet(final_map, labels, 4, args.triplet_margin)
                preservation_loss = 1.0 - F.cosine_similarity(features, teacher_features).mean()
                loss = (
                    args.arc_weight * arc_loss
                    + args.classifier_weight * classifier_loss
                    + args.triplet_weight * triplet_loss
                    + args.part_weight * local_loss
                    + args.teacher_weight * preservation_loss
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_([*trainable_base, *trainable_neck, *arc_head.parameters()], 5.0)
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running["loss"] += float(loss.detach())
            running["arc"] += float(arc_loss.detach())
            running["classifier"] += float(classifier_loss.detach())
            running["triplet"] += float(triplet_loss.detach())
            running["part"] += float(local_loss.detach())
            running["teacher"] += float(preservation_loss.detach())
        vectors = encode_rows(args.root, validation_rows, student, eval_transform, device, args.eval_batch_size)
        validation = strict_closed_set_metrics(validation_rows, vectors)
        row: dict[str, object] = {
            "epoch": epoch,
            "losses": {name: value / args.steps_per_epoch for name, value in sorted(running.items())},
            "validation": validation,
        }
        history.append(row)
        print(json.dumps(row, sort_keys=True), flush=True)
        key = validation_key(validation)
        if key > best_key:
            best_key = key
            best_epoch = epoch
            best_validation = validation
            save_production_checkpoint(student, args.output_checkpoint)
    selected_sha = hashlib.sha256(args.output_checkpoint.read_bytes()).hexdigest()
    result = {
        "schemaVersion": "chirla-solider-identity-heldout-finetune-v1",
        "status": "valid",
        "manifestSha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "sourceCheckpointSha256": actual_source_sha,
        "selectedCheckpointSha256": selected_sha,
        "soliderRuntimeId": args.solider_runtime_id,
        "soliderMakeModelSha256": solider_runtime_sha,
        "trainIdentities": train_identities,
        "trainRows": len(train_rows),
        "validationRows": len(validation_rows),
        "trainableParameters": sum(parameter.numel() for parameter in student.parameters() if parameter.requires_grad) + sum(parameter.numel() for parameter in arc_head.parameters()),
        "losses": {"ArcFace": True, "rawClassifier": True, "batchHardTriplet": True, "partTriplet": True, "teacherPreservation": True},
        "baselineValidation": baseline,
        "bestEpoch": best_epoch,
        "bestValidation": best_validation,
        "history": history,
        "sealedEvaluationRead": False,
        "checkpointClassifierOmitted": True,
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"bestEpoch": best_epoch, "bestValidation": best_validation, "checkpointSha256": selected_sha}, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
