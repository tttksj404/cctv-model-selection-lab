from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import asdict
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
from scripts.prid2011_track_metrics import (
    TrackEmbedding,
    calibrate_open_set,
    evaluate_retrieval,
    pool_tracks,
)


class ManifestRow(TypedDict):
    localPath: str
    sha256: str
    identityGroupId: str
    cameraId: str
    trackId: str
    benchmarkRole: str
    split: str


class FinetuneError(RuntimeError):
    pass


class ArcMarginHead(nn.Module):
    def __init__(
        self,
        feature_dim: int,
        classes: int,
        *,
        scale: float,
        margin: float,
    ) -> None:
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
        angular = torch.where(
            cosine > self.threshold,
            angular,
            cosine - self.margin_adjustment,
        )
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(
            dtype=cosine.dtype
        )
        return self.scale * (one_hot * angular + (1.0 - one_hot) * cosine)


def batch_hard_triplet(
    features: torch.Tensor,
    labels: torch.Tensor,
    *,
    margin: float,
) -> torch.Tensor:
    normalized = F.normalize(features)
    distances = torch.cdist(normalized, normalized, p=2)
    same = labels[:, None].eq(labels[None, :])
    same.fill_diagonal_(False)
    different = ~labels[:, None].eq(labels[None, :])
    positive = distances.masked_fill(~same, float("-inf")).max(dim=1).values
    negative = distances.masked_fill(~different, float("inf")).min(dim=1).values
    valid = torch.isfinite(positive) & torch.isfinite(negative)
    if not bool(valid.any()):
        raise FinetuneError("batch-hard triplet requires positive and negative pairs")
    return F.softplus(positive[valid] - negative[valid] + margin).mean()


def part_triplet(
    feature_map: torch.Tensor,
    labels: torch.Tensor,
    *,
    parts: int,
    margin: float,
) -> torch.Tensor:
    if feature_map.ndim != 4:
        raise FinetuneError("SOLIDER final feature map must be BCHW")
    stripes = torch.tensor_split(feature_map, parts, dim=2)
    losses = [
        batch_hard_triplet(
            stripe.mean(dim=(2, 3)),
            labels,
            margin=margin,
        )
        for stripe in stripes
        if stripe.shape[2] > 0
    ]
    return torch.stack(losses).mean()


def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise FinetuneError(f"manifest field {key!r} must be non-empty text")
    return value


def load_manifest(root: Path, manifest: Path) -> list[ManifestRow]:
    rows: list[ManifestRow] = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        raw: object = json.loads(line)
        if not isinstance(raw, dict):
            raise FinetuneError("manifest lines must be JSON objects")
        row: ManifestRow = {
            "localPath": _text(raw, "localPath"),
            "sha256": _text(raw, "sha256"),
            "identityGroupId": _text(raw, "identityGroupId"),
            "cameraId": _text(raw, "cameraId"),
            "trackId": _text(raw, "trackId"),
            "benchmarkRole": _text(raw, "benchmarkRole"),
            "split": _text(raw, "split"),
        }
        image = root / row["localPath"]
        if not image.is_file():
            raise FileNotFoundError(image)
        if hashlib.sha256(image.read_bytes()).hexdigest() != row["sha256"]:
            raise FinetuneError(f"sha256 mismatch: {image}")
        rows.append(row)
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
        grouped: dict[str, dict[str, list[ManifestRow]]] = defaultdict(
            lambda: defaultdict(list)
        )
        for row in rows:
            grouped[row["identityGroupId"]][row["cameraId"]].append(row)
        self.grouped = {
            identity: dict(cameras)
            for identity, cameras in grouped.items()
            if len(cameras) >= 2
        }
        self.identities = sorted(self.grouped)
        self.identity_index = {
            identity: index for index, identity in enumerate(self.identities)
        }
        self.identities_per_batch = identities_per_batch
        self.images_per_identity = images_per_identity
        self.rng = random.Random(seed)
        if len(self.identities) < identities_per_batch:
            raise FinetuneError(
                "balanced sampler has fewer identities than identities_per_batch"
            )
        if images_per_identity < 2:
            raise FinetuneError("images_per_identity must be at least two")

    def sample(self) -> tuple[list[ManifestRow], list[int]]:
        selected = self.rng.sample(self.identities, self.identities_per_batch)
        rows: list[ManifestRow] = []
        labels: list[int] = []
        for identity in selected:
            by_camera = self.grouped[identity]
            cameras = sorted(by_camera)
            picked = [
                self.rng.choice(by_camera[cameras[0]]),
                self.rng.choice(by_camera[cameras[1]]),
            ]
            all_rows = [row for camera_rows in by_camera.values() for row in camera_rows]
            while len(picked) < self.images_per_identity:
                picked.append(self.rng.choice(all_rows))
            rows.extend(picked)
            label = self.identity_index[identity]
            labels.extend([label] * len(picked))
        return rows, labels


def _load_batch(
    root: Path,
    rows: Sequence[ManifestRow],
    transform: Compose,
    device: torch.device,
) -> torch.Tensor:
    images: list[torch.Tensor] = []
    for row in rows:
        with Image.open(root / row["localPath"]) as image:
            images.append(transform(image.convert("RGB")))
    return torch.stack(images).to(device, non_blocking=True)


def _encode_rows(
    root: Path,
    rows: Sequence[ManifestRow],
    model: nn.Module,
    transform: Compose,
    device: torch.device,
    batch_size: int,
) -> np.ndarray:
    chunks: list[np.ndarray] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            inputs = _load_batch(
                root,
                rows[start : start + batch_size],
                transform,
                device,
            )
            output = model(inputs)
            if not isinstance(output, tuple) or not isinstance(output[0], torch.Tensor):
                raise FinetuneError("SOLIDER inference output is not a feature tuple")
            features = output[0]
            flipped = model(torch.flip(inputs, dims=(3,)))
            if not isinstance(flipped, tuple) or not isinstance(
                flipped[0], torch.Tensor
            ):
                raise FinetuneError("SOLIDER flipped output is not a feature tuple")
            features = F.normalize(features) + F.normalize(flipped[0])
            chunks.append(F.normalize(features).float().cpu().numpy())
    return np.concatenate(chunks)


def _validation_metrics(
    root: Path,
    rows: Sequence[ManifestRow],
    model: nn.Module,
    transform: Compose,
    device: torch.device,
    batch_size: int,
) -> dict[str, int | float]:
    validation_rows = [row for row in rows if row["split"] == "validation"]
    vectors = _encode_rows(
        root,
        validation_rows,
        model,
        transform,
        device,
        batch_size,
    )
    tracks = pool_tracks(
        cast(list[dict[str, object]], validation_rows),
        vectors,
    )
    calibration = calibrate_open_set(tracks)
    return {
        **asdict(evaluate_retrieval(tracks, calibration)),
        **_continuous_validation_metrics(tracks),
    }


def _continuous_validation_metrics(
    tracks: Sequence[TrackEmbedding],
) -> dict[str, float]:
    queries = [track for track in tracks if track.role == "query"]
    gallery = [track for track in tracks if track.role == "gallery"]
    if not queries or len(gallery) < 2:
        raise FinetuneError(
            "continuous validation requires queries and at least two gallery tracks"
        )
    gallery_vectors = np.stack([track.vector for track in gallery])
    gallery_identities = np.asarray([track.identity for track in gallery])
    positive_scores: list[float] = []
    hard_negative_scores: list[float] = []
    known_margins: list[float] = []
    distractor_top1_scores: list[float] = []
    for query in queries:
        scores = gallery_vectors @ query.vector
        positive_mask = gallery_identities == query.identity
        if bool(positive_mask.any()):
            negative_mask = ~positive_mask
            if not bool(negative_mask.any()):
                raise FinetuneError(
                    "continuous validation requires negative gallery identities"
                )
            positive = float(np.max(scores[positive_mask]))
            hard_negative = float(np.max(scores[negative_mask]))
            positive_scores.append(positive)
            hard_negative_scores.append(hard_negative)
            known_margins.append(positive - hard_negative)
        else:
            distractor_top1_scores.append(float(np.max(scores)))
    if not positive_scores or not distractor_top1_scores:
        raise FinetuneError(
            "continuous validation requires known and distractor queries"
        )
    return {
        "known_positive_mean_similarity": float(np.mean(positive_scores)),
        "known_hard_negative_mean_similarity": float(
            np.mean(hard_negative_scores)
        ),
        "known_separation_margin_mean": float(np.mean(known_margins)),
        "known_separation_margin_p10": float(np.quantile(known_margins, 0.10)),
        "distractor_top1_mean_similarity": float(
            np.mean(distractor_top1_scores)
        ),
        "distractor_top1_p95_similarity": float(
            np.quantile(distractor_top1_scores, 0.95)
        ),
        "known_distractor_score_gap": float(
            np.quantile(positive_scores, 0.10)
            - np.quantile(distractor_top1_scores, 0.95)
        ),
    }


def _validation_key(metrics: dict[str, int | float]) -> tuple[float, ...]:
    return (
        float(metrics["automatic_decision_accuracy"]),
        float(metrics["known_rank1"]),
        float(metrics["known_recall_at5"]),
        -float(metrics["distractor_false_match_rate"]),
        -float(metrics["false_reject_rate"]),
        float(metrics["known_distractor_score_gap"]),
        float(metrics["known_separation_margin_p10"]),
        float(metrics["known_separation_margin_mean"]),
        -float(metrics["distractor_top1_p95_similarity"]),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fine-tune SOLIDER last-stage features with ArcFace, batch-hard global/"
            "part triplet, cross-camera sampling, and teacher preservation"
        )
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--solider-root", type=Path, required=True)
    parser.add_argument("--output-checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda:0")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--warmup-epochs", type=int, default=2)
    parser.add_argument("--steps-per-epoch", type=int, default=50)
    parser.add_argument("--identities-per-batch", type=int, default=8)
    parser.add_argument("--images-per-identity", type=int, default=4)
    parser.add_argument("--eval-every", type=int, default=2)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--backbone-lr", type=float, default=2e-6)
    parser.add_argument("--head-lr", type=float, default=3e-4)
    parser.add_argument("--weight-decay", type=float, default=1e-4)
    parser.add_argument("--triplet-weight", type=float, default=1.0)
    parser.add_argument("--part-weight", type=float, default=0.20)
    parser.add_argument("--teacher-weight", type=float, default=1.0)
    parser.add_argument("--triplet-margin", type=float, default=0.20)
    parser.add_argument("--arc-margin", type=float, default=0.20)
    parser.add_argument("--arc-scale", type=float, default=32.0)
    parser.add_argument("--seed", type=int, default=20260729)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not torch.cuda.is_available() and str(args.device).startswith("cuda"):
        raise FinetuneError("CUDA device requested but CUDA is unavailable")
    torch.manual_seed(args.seed)
    np.random.seed(args.seed)
    random.seed(args.seed)
    device = torch.device(args.device)
    rows = load_manifest(args.root, args.manifest)
    train_rows = [row for row in rows if row["split"] == "train"]
    train_identities = sorted({row["identityGroupId"] for row in train_rows})
    sampler = BalancedIdentitySampler(
        train_rows,
        identities_per_batch=args.identities_per_batch,
        images_per_identity=args.images_per_identity,
        seed=args.seed,
    )
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
    trainable_base: list[nn.Parameter] = []
    trainable_neck: list[nn.Parameter] = []
    for name, parameter in student.named_parameters():
        if name.startswith("base.stages.3.") or name.startswith("base.norm"):
            parameter.requires_grad_(True)
            trainable_base.append(parameter)
        elif name.startswith("bottleneck."):
            parameter.requires_grad_(True)
            trainable_neck.append(parameter)
    feature_dim = 1024
    student.classifier = nn.Linear(
        feature_dim,
        len(train_identities),
        bias=False,
        device=device,
    )
    for parameter in student.classifier.parameters():
        trainable_neck.append(parameter)
    arc_head = ArcMarginHead(
        feature_dim,
        len(train_identities),
        scale=args.arc_scale,
        margin=args.arc_margin,
    ).to(device)
    eval_transform = cast(Compose, student_encoder.processor)
    resize_transform = eval_transform.transforms[0]
    normalize_transform = eval_transform.transforms[-1]
    train_transform = Compose(
        [
            resize_transform,
            Pad(10),
            RandomCrop((384, 128)),
            RandomHorizontalFlip(),
            ColorJitter(brightness=0.25, contrast=0.25, saturation=0.20, hue=0.05),
            RandomGrayscale(p=0.05),
            ToTensor(),
            normalize_transform,
            RandomErasing(p=0.50, scale=(0.02, 0.25), ratio=(0.3, 3.3)),
        ]
    )
    optimizer = torch.optim.AdamW(
        [
            {"params": trainable_base, "lr": args.backbone_lr},
            {"params": trainable_neck, "lr": args.head_lr},
            {"params": arc_head.parameters(), "lr": args.head_lr},
        ],
        weight_decay=args.weight_decay,
    )
    total_steps = args.epochs * args.steps_per_epoch
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(1, total_steps),
    )
    scaler = torch.amp.GradScaler("cuda", enabled=device.type == "cuda")
    history: list[dict[str, object]] = []
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    baseline = _validation_metrics(
        args.root,
        rows,
        student,
        eval_transform,
        device,
        args.eval_batch_size,
    )
    print(json.dumps({"epoch": 0, "validation": baseline}, sort_keys=True), flush=True)
    best_key = _validation_key(baseline)
    best_epoch = 0
    best_validation: dict[str, int | float] = baseline
    torch.save(student.state_dict(), args.output_checkpoint)
    for epoch in range(1, args.epochs + 1):
        backbone_enabled = epoch > args.warmup_epochs
        for parameter in trainable_base:
            parameter.requires_grad_(backbone_enabled)
        student.train()
        running = defaultdict(float)
        for _ in range(args.steps_per_epoch):
            batch_rows, label_rows = sampler.sample()
            inputs = _load_batch(
                args.root,
                batch_rows,
                train_transform,
                device,
            )
            labels = torch.tensor(label_rows, dtype=torch.long, device=device)
            optimizer.zero_grad(set_to_none=True)
            with torch.inference_mode():
                teacher_output = teacher(inputs)
                if not isinstance(teacher_output, tuple) or not isinstance(
                    teacher_output[0], torch.Tensor
                ):
                    raise FinetuneError("teacher did not return a feature tuple")
                teacher_features = teacher_output[0]
            with torch.autocast(
                device_type=device.type,
                dtype=torch.float16,
                enabled=device.type == "cuda",
            ):
                output = student(inputs, label=labels)
                if (
                    not isinstance(output, tuple)
                    or len(output) < 3
                    or not isinstance(output[1], torch.Tensor)
                    or not isinstance(output[2], list)
                    or not output[2]
                    or not isinstance(output[2][-1], torch.Tensor)
                ):
                    raise FinetuneError("student did not return training features")
                features = output[1]
                final_map = output[2][-1]
                arc_loss = F.cross_entropy(
                    arc_head(features, labels),
                    labels,
                    label_smoothing=0.10,
                )
                triplet_loss = batch_hard_triplet(
                    features,
                    labels,
                    margin=args.triplet_margin,
                )
                local_loss = part_triplet(
                    final_map,
                    labels,
                    parts=4,
                    margin=args.triplet_margin,
                )
                preservation_loss = 1.0 - F.cosine_similarity(
                    features,
                    teacher_features,
                ).mean()
                loss = (
                    arc_loss
                    + args.triplet_weight * triplet_loss
                    + args.part_weight * local_loss
                    + args.teacher_weight * preservation_loss
                )
            scaler.scale(loss).backward()
            scaler.unscale_(optimizer)
            torch.nn.utils.clip_grad_norm_(
                [*trainable_base, *trainable_neck, *arc_head.parameters()],
                max_norm=5.0,
            )
            scaler.step(optimizer)
            scaler.update()
            scheduler.step()
            running["loss"] += float(loss.detach())
            running["arc"] += float(arc_loss.detach())
            running["triplet"] += float(triplet_loss.detach())
            running["part"] += float(local_loss.detach())
            running["preservation"] += float(preservation_loss.detach())
        epoch_row: dict[str, object] = {
            "epoch": epoch,
            "losses": {
                name: value / args.steps_per_epoch
                for name, value in sorted(running.items())
            },
        }
        if epoch % args.eval_every == 0 or epoch == args.epochs:
            validation = _validation_metrics(
                args.root,
                rows,
                student,
                eval_transform,
                device,
                args.eval_batch_size,
            )
            epoch_row["validation"] = validation
            key = _validation_key(validation)
            if key > best_key:
                best_key = key
                best_epoch = epoch
                best_validation = validation
                torch.save(student.state_dict(), args.output_checkpoint)
        history.append(epoch_row)
        print(json.dumps(epoch_row, sort_keys=True), flush=True)
    result = {
        "schemaVersion": "prid2011-solider-finetune-v2",
        "status": "valid",
        "checkpoint": str(args.output_checkpoint),
        "sourceCheckpoint": str(args.checkpoint),
        "sourceCheckpointSha256": hashlib.sha256(
            args.checkpoint.read_bytes()
        ).hexdigest(),
        "manifestSha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "trainIdentities": len(train_identities),
        "trainFrames": len(train_rows),
        "trainableParameters": sum(
            parameter.numel()
            for parameter in student.parameters()
            if parameter.requires_grad
        )
        + sum(parameter.numel() for parameter in arc_head.parameters()),
        "losses": {
            "arcFace": True,
            "batchHardTriplet": True,
            "partTriplet": True,
            "teacherPreservation": True,
        },
        "baselineValidation": baseline,
        "bestEpoch": best_epoch,
        "bestValidation": best_validation,
        "history": history,
        "testEvaluatedDuringTraining": False,
    }
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(
        json.dumps(
            {
                "selectedCheckpoint": str(args.output_checkpoint),
                "bestValidation": best_validation,
            },
            sort_keys=True,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

