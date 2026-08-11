from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional as F
from transformers import CLIPModel, AutoProcessor

TARGET_IDENTITIES = ("1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14")
DISTRACTOR_IDENTITIES = ("-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11")


def parse_identity_list(raw: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if raw is None:
        return default
    values = tuple(value.strip() for value in raw.split(",") if value.strip())
    if not values or len(values) != len(set(values)):
        raise ValueError("identity list must contain unique non-empty values")
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _role(row: dict[str, Any]) -> str:
    split = str(row.get("split", ""))
    subset = str(row.get("subset", ""))
    if split == "train" and subset == "train_0":
        return "train"
    if split == "test" and subset == "test_0":
        return "validation"
    if split == "train":
        return "gallery"
    if split == "test":
        return "query"
    raise ValueError(f"unsupported split: {split}")


def load_rows(root: Path, manifest: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict) or str(row.get("identityGroupId", "")) == "":
            raise ValueError(f"invalid manifest row {line_number}")
        relative = Path(str(row["localPath"]))
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(path)
        row["identityGroupId"] = str(row["identityGroupId"])
        row["benchmarkRole"] = _role(row)
        row["_path"] = str(path)
        rows.append(row)
    return rows


def color_features(paths: list[Path]) -> Tensor:
    values: list[np.ndarray] = []
    for path in paths:
        with Image.open(path) as image:
            array = np.asarray(image.convert("RGB").resize((96, 192)), dtype=np.float32) / 255.0
        hsv = (
            np.asarray(
                Image.fromarray((array * 255).astype(np.uint8), mode="RGB").convert("HSV"),
                dtype=np.float32,
            )
            / 255.0
        )
        regions = np.array_split(hsv, 4, axis=0)
        row: list[float] = []
        for region in regions:
            for channel, bins in ((region[:, :, 0], 8), (region[:, :, 1], 4), (region[:, :, 2], 4)):
                histogram, _ = np.histogram(channel, bins=bins, range=(0.0, 1.0))
                row.extend((histogram / max(float(histogram.sum()), 1.0)).tolist())
        values.append(np.asarray(row, dtype=np.float32))
    return torch.from_numpy(np.stack(values))


def clip_features(
    rows: list[dict[str, Any]],
    model: Any,
    processor: Any,
    device: torch.device,
    batch_size: int,
) -> Tensor:
    paths = [Path(str(row["_path"])) for row in rows]
    chunks: list[Tensor] = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(paths), batch_size):
            images = []
            for path in paths[start : start + batch_size]:
                with Image.open(path) as image:
                    images.append(image.convert("RGB"))
            inputs = processor(images=images, return_tensors="pt")
            inputs = {key: value.to(device) for key, value in inputs.items()}
            vision_output = model.vision_model(pixel_values=inputs["pixel_values"])
            encoded = model.visual_projection(vision_output.pooler_output)
            if not isinstance(encoded, Tensor):
                raise RuntimeError("CLIP image feature output is not a tensor")
            chunks.append(F.normalize(encoded.float(), dim=-1).cpu())
    return torch.cat(chunks)


def _track_key(row: dict[str, Any]) -> str:
    return "|".join(
        str(row.get(key, "")) for key in ("identityGroupId", "sequenceId", "cameraId", "subset")
    )


def track_vectors(
    rows: list[dict[str, Any]], features: Tensor, pooling: str = "mean"
) -> tuple[list[dict[str, Any]], Tensor]:
    if pooling not in {"mean", "quality"}:
        raise ValueError(f"unsupported track pooling: {pooling}")
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[_track_key(row)].append(index)
    track_rows: list[dict[str, Any]] = []
    vectors: list[Tensor] = []
    for key, indices in sorted(groups.items()):
        row = dict(rows[indices[0]])
        row["trackKey"] = key
        row["frameCount"] = len(indices)
        track_rows.append(row)
        if pooling == "mean":
            pooled = features[indices].mean(dim=0)
        else:
            quality: list[float] = []
            for index in indices:
                with Image.open(str(rows[index]["_path"])) as image:
                    gray = np.asarray(image.convert("L").resize((64, 128)), dtype=np.float32) / 255.0
                gx = np.abs(np.diff(gray, axis=1)).mean()
                gy = np.abs(np.diff(gray, axis=0)).mean()
                exposure = 1.0 - min(abs(float(gray.mean()) - 0.5) * 2.0, 1.0)
                quality.append(float((gx + gy) * (0.5 + 0.5 * exposure) + 1e-6))
            weights = torch.tensor(quality, dtype=features.dtype, device=features.device)
            weights = weights / weights.sum().clamp_min(1e-8)
            pooled = (features[indices] * weights[:, None]).sum(dim=0)
        vectors.append(F.normalize(pooled, dim=0))
    return track_rows, torch.stack(vectors)


class Adapter(nn.Module):
    def __init__(self, input_dim: int, hidden_dim: int = 512, output_dim: int = 256) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.GELU(),
            nn.Dropout(0.1),
            nn.Linear(hidden_dim, output_dim),
        )

    def forward(self, values: Tensor) -> Tensor:
        return F.normalize(self.layers(values), dim=-1)


class ArcFaceHead(nn.Module):
    def __init__(self, input_dim: int, class_count: int, scale: float = 30.0, margin: float = 0.35) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.empty(class_count, input_dim))
        nn.init.xavier_uniform_(self.weight)
        self.scale = scale
        self.margin = margin

    def forward(self, embeddings: Tensor, labels: Tensor) -> Tensor:
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        sine = torch.sqrt(torch.clamp(1.0 - cosine.square(), min=1e-7))
        phi = cosine * math.cos(self.margin) - sine * math.sin(self.margin)
        threshold = math.cos(math.pi - self.margin)
        phi = torch.where(
            cosine > threshold,
            phi,
            cosine - math.sin(math.pi - self.margin) * self.margin,
        )
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(cosine.dtype)
        return self.scale * (one_hot * phi + (1.0 - one_hot) * cosine)


class CosFaceHead(nn.Module):
    def __init__(self, input_dim: int, class_count: int, scale: float = 30.0, margin: float = 0.35) -> None:
        super().__init__()
        self.weight = nn.Parameter(torch.empty(class_count, input_dim))
        nn.init.xavier_uniform_(self.weight)
        self.scale = scale
        self.margin = margin

    def forward(self, embeddings: Tensor, labels: Tensor) -> Tensor:
        cosine = F.linear(F.normalize(embeddings), F.normalize(self.weight))
        one_hot = F.one_hot(labels, num_classes=self.weight.shape[0]).to(cosine.dtype)
        return self.scale * (cosine - one_hot * self.margin)


def supervised_contrastive_loss(embeddings: Tensor, labels: Tensor, temperature: float) -> Tensor:
    logits = embeddings @ embeddings.T / temperature
    diagonal = torch.eye(len(embeddings), device=embeddings.device, dtype=torch.bool)
    logits = logits.masked_fill(diagonal, -torch.inf)
    positive = labels[:, None].eq(labels[None, :]) & ~diagonal
    valid = positive.any(dim=1)
    if not bool(valid.any()):
        raise ValueError("training batch has no positive pairs")
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    return -(log_prob.masked_fill(~positive, 0.0).sum(dim=1) / positive.sum(dim=1).clamp_min(1))[
        valid
    ].mean()


def batch_hard_triplet_loss(embeddings: Tensor, labels: Tensor, margin: float) -> Tensor:
    distances = 1.0 - embeddings @ embeddings.T
    diagonal = torch.eye(len(embeddings), device=embeddings.device, dtype=torch.bool)
    positive = labels[:, None].eq(labels[None, :]) & ~diagonal
    negative = labels[:, None].ne(labels[None, :])
    valid = positive.any(dim=1) & negative.any(dim=1)
    if not bool(valid.any()):
        raise ValueError("training batch has no valid triplets")
    hardest_positive = distances.masked_fill(~positive, -torch.inf).max(dim=1).values
    hardest_negative = distances.masked_fill(~negative, torch.inf).min(dim=1).values
    return F.relu(hardest_positive - hardest_negative + margin)[valid].mean()


def circle_loss(embeddings: Tensor, labels: Tensor, margin: float = 0.25, gamma: float = 32.0) -> Tensor:
    similarity = embeddings @ embeddings.T
    diagonal = torch.eye(len(embeddings), device=embeddings.device, dtype=torch.bool)
    positive = labels[:, None].eq(labels[None, :]) & ~diagonal
    negative = labels[:, None].ne(labels[None, :])
    valid = positive.any(dim=1) & negative.any(dim=1)
    if not bool(valid.any()):
        raise ValueError("training batch has no valid circle pairs")
    positive_logits = similarity.masked_fill(~positive, -torch.inf)
    negative_logits = similarity.masked_fill(~negative, -torch.inf)
    alpha_positive = F.relu(1.0 + margin - positive_logits.detach())
    alpha_negative = F.relu(negative_logits.detach() + margin)
    positive_term = -gamma * alpha_positive * (positive_logits - (1.0 - margin))
    negative_term = gamma * alpha_negative * (negative_logits - margin)
    positive_term = positive_term.masked_fill(~positive, -torch.inf)
    negative_term = negative_term.masked_fill(~negative, -torch.inf)
    per_anchor = torch.logsumexp(positive_term, dim=1) + torch.logsumexp(negative_term, dim=1)
    return F.softplus(per_anchor[valid]).mean()


def train_adapter(
    features: Tensor,
    labels: Tensor,
    device: torch.device,
    epochs: int,
    seed: int,
    objective: str,
    class_count: int,
    teacher_features: Tensor | None = None,
) -> Adapter:
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    adapter = Adapter(features.shape[1]).to(device)
    classifier = nn.Linear(256, class_count).to(device)
    use_arcface = objective in ("supcon_arcface_triplet", "supcon_arcface_triplet_kd")
    use_cosface = objective in ("supcon_cosface_triplet", "supcon_cosface_triplet_kd")
    use_kd = objective.endswith("_kd")
    if use_kd and teacher_features is None:
        raise ValueError("KD objective requires teacher_features")
    if not use_kd and teacher_features is not None:
        raise ValueError("teacher_features require a *_kd objective")
    arcface = ArcFaceHead(256, class_count).to(device) if use_arcface else None
    cosface = CosFaceHead(256, class_count).to(device) if use_cosface else None
    trainable_heads = (
        arcface.parameters()
        if arcface is not None
        else cosface.parameters()
        if cosface is not None
        else classifier.parameters()
    )
    optimizer = torch.optim.AdamW(
        (*adapter.parameters(), *trainable_heads), lr=0.0005, weight_decay=0.01
    )
    source = F.normalize(features.to(device), dim=-1)
    target = labels.to(device)
    teacher_source = F.normalize(teacher_features.to(device), dim=-1) if use_kd else None
    teacher_similarity = teacher_source @ teacher_source.T / 0.07 if teacher_source is not None else None
    for _ in range(epochs):
        noise = torch.randn_like(source) * 0.003
        embeddings = adapter(F.normalize(source + noise, dim=-1))
        loss = supervised_contrastive_loss(embeddings, target, temperature=0.07)
        if objective in (
            "supcon_ce",
            "supcon_ce_triplet",
            "supcon_ce_triplet_kd",
            "supcon_arcface_triplet",
            "supcon_arcface_triplet_kd",
            "supcon_cosface_triplet",
            "supcon_cosface_triplet_kd",
            "supcon_circle_triplet",
            "supcon_circle_triplet_kd",
        ):
            if arcface is not None:
                logits = arcface(embeddings, target)
            elif cosface is not None:
                logits = cosface(embeddings, target)
            else:
                logits = classifier(embeddings)
            loss = loss + 0.5 * F.cross_entropy(logits, target)
        if "triplet" in objective:
            loss = loss + 0.5 * batch_hard_triplet_loss(embeddings, target, margin=0.3)
        if "circle" in objective:
            loss = loss + 0.5 * circle_loss(embeddings, target)
        if use_kd:
            student_similarity = embeddings @ embeddings.T / 0.07
            loss = loss + 0.25 * F.smooth_l1_loss(student_similarity, teacher_similarity)
        optimizer.zero_grad(set_to_none=True)
        loss.backward()
        optimizer.step()
    return adapter.eval()


def _identity_prototypes(
    rows: list[dict[str, Any]], vectors: Tensor, identities: list[str]
) -> Tensor:
    prototypes = []
    for identity in identities:
        indices = [index for index, row in enumerate(rows) if row["identityGroupId"] == identity]
        if not indices:
            raise ValueError(f"gallery identity has no rows: {identity}")
        prototypes.append(F.normalize(vectors[indices].mean(dim=0), dim=0))
    return torch.stack(prototypes)


def _score_matrix(
    rows: list[dict[str, Any]],
    vectors: Tensor,
    gallery_aggregation: str,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
    track_pooling: str = "mean",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], Tensor]:
    gallery_rows, gallery_vectors = track_vectors(
        [
            row
            for row in rows
            if row["benchmarkRole"] == "gallery" and row["identityGroupId"] in target_identities
        ],
        vectors[
            [
                index
                for index, row in enumerate(rows)
                if row["benchmarkRole"] == "gallery" and row["identityGroupId"] in target_identities
            ]
        ],
        track_pooling,
    )
    query_rows, query_vectors = track_vectors(
        [
            row
            for row in rows
            if row["benchmarkRole"] == "query"
            and row["identityGroupId"] in (*target_identities, *distractor_identities)
        ],
        vectors[
            [
                index
                for index, row in enumerate(rows)
                if row["benchmarkRole"] == "query"
                and row["identityGroupId"] in (*target_identities, *distractor_identities)
            ]
        ],
        track_pooling,
    )
    identities = list(target_identities)
    if gallery_aggregation == "prototype":
        prototypes = _identity_prototypes(gallery_rows, gallery_vectors, identities)
        scores = query_vectors @ prototypes.T
    else:
        score_columns = []
        for identity in identities:
            indices = [
                index
                for index, row in enumerate(gallery_rows)
                if row["identityGroupId"] == identity
            ]
            identity_scores = query_vectors @ gallery_vectors[indices].T
            if gallery_aggregation == "max":
                score_columns.append(identity_scores.max(dim=1).values)
            else:
                prototype_scores = identity_scores.mean(dim=1)
                max_scores = identity_scores.max(dim=1).values
                score_columns.append(0.5 * prototype_scores + 0.5 * max_scores)
        scores = torch.stack(score_columns, dim=1)
    return gallery_rows, query_rows, scores


def _metrics(
    gallery_rows: list[dict[str, Any]],
    query_rows: list[dict[str, Any]],
    scores: Tensor,
    threshold: float,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
) -> dict[str, Any]:
    identities = list(target_identities)
    target_indices = [
        index for index, row in enumerate(query_rows) if row["identityGroupId"] in target_identities
    ]
    distractor_indices = [
        index
        for index, row in enumerate(query_rows)
        if row["identityGroupId"] in distractor_identities
    ]
    ranks = []
    for index in target_indices:
        order = torch.argsort(scores[index], descending=True)
        relevant = torch.where(
            torch.tensor(
                [identities[item] == query_rows[index]["identityGroupId"] for item in order]
            )
        )[0]
        ranks.append(int(relevant[0]) + 1)
    distractor_scores = (
        scores[distractor_indices].max(dim=1).values if distractor_indices else torch.empty(0)
    )
    return {
        "galleryTrackCount": len(gallery_rows),
        "queryTrackCount": len(query_rows),
        "targetQueryTrackCount": len(target_indices),
        "distractorQueryTrackCount": len(distractor_indices),
        "rank1": float(np.mean(np.asarray(ranks) == 1)) if ranks else 0.0,
        "recallAt5": float(np.mean(np.asarray(ranks) <= 5)) if ranks else 0.0,
        "falseMatchRate": float((distractor_scores >= threshold).float().mean())
        if len(distractor_scores)
        else 0.0,
        "falseRejectRate": float(
            (scores[target_indices].max(dim=1).values < threshold).float().mean()
        )
        if target_indices
        else 0.0,
        "threshold": threshold,
    }


def _margin_metrics(
    gallery_rows: list[dict[str, Any]],
    query_rows: list[dict[str, Any]],
    scores: Tensor,
    threshold: float,
    margin_threshold: float,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
) -> dict[str, Any]:
    result = _metrics(
        gallery_rows,
        query_rows,
        scores,
        threshold,
        target_identities,
        distractor_identities,
    )
    order = torch.argsort(scores, dim=1, descending=True)
    top_scores = scores.gather(1, order[:, : min(2, scores.shape[1])])
    if scores.shape[1] < 2:
        margins = torch.full(
            (scores.shape[0],),
            torch.inf,
            dtype=scores.dtype,
            device=scores.device,
        )
    else:
        margins = top_scores[:, 0] - top_scores[:, 1]
    target_indices = [
        index for index, row in enumerate(query_rows) if row["identityGroupId"] in target_identities
    ]
    distractor_indices = [
        index
        for index, row in enumerate(query_rows)
        if row["identityGroupId"] in distractor_identities
    ]
    accepted = (top_scores[:, 0] >= threshold) & (margins >= margin_threshold)
    result["marginThreshold"] = margin_threshold
    result["acceptedTargetRate"] = float(accepted[target_indices].float().mean())
    result["falseMatchRate"] = (
        float(accepted[distractor_indices].float().mean()) if distractor_indices else 0.0
    )
    result["falseRejectRate"] = float((~accepted[target_indices]).float().mean())
    result["acceptedTargetTrackCount"] = int(accepted[target_indices].sum())
    result["acceptedDistractorTrackCount"] = int(accepted[distractor_indices].sum())
    return result


def evaluate(
    rows: list[dict[str, Any]],
    vectors: Tensor,
    threshold: float,
    gallery_aggregation: str,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
    track_pooling: str = "mean",
) -> dict[str, Any]:
    gallery_rows, query_rows, scores = _score_matrix(
        rows,
        vectors,
        gallery_aggregation,
        target_identities,
        distractor_identities,
        track_pooling,
    )
    return _metrics(
        gallery_rows,
        query_rows,
        scores,
        threshold,
        target_identities,
        distractor_identities,
    )


def evaluate_score_blend(
    rows: list[dict[str, Any]],
    base_vectors: Tensor,
    learned_vectors: Tensor,
    alpha: float,
    threshold: float,
    gallery_aggregation: str,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
    track_pooling: str = "mean",
) -> dict[str, Any]:
    gallery_rows, query_rows, base_scores = _score_matrix(
        rows,
        base_vectors,
        gallery_aggregation,
        target_identities,
        distractor_identities,
        track_pooling,
    )
    _, _, learned_scores = _score_matrix(
        rows,
        learned_vectors,
        gallery_aggregation,
        target_identities,
        distractor_identities,
        track_pooling,
    )
    return _metrics(
        gallery_rows,
        query_rows,
        alpha * learned_scores + (1.0 - alpha) * base_scores,
        threshold,
        target_identities,
        distractor_identities,
    )


def evaluate_score_blend_margin(
    rows: list[dict[str, Any]],
    base_vectors: Tensor,
    learned_vectors: Tensor,
    alpha: float,
    threshold: float,
    margin_threshold: float,
    gallery_aggregation: str,
    target_identities: tuple[str, ...],
    distractor_identities: tuple[str, ...],
    track_pooling: str = "mean",
) -> dict[str, Any]:
    gallery_rows, query_rows, base_scores = _score_matrix(
        rows,
        base_vectors,
        gallery_aggregation,
        target_identities,
        distractor_identities,
        track_pooling,
    )
    _, _, learned_scores = _score_matrix(
        rows,
        learned_vectors,
        gallery_aggregation,
        target_identities,
        distractor_identities,
        track_pooling,
    )
    return _margin_metrics(
        gallery_rows,
        query_rows,
        alpha * learned_scores + (1.0 - alpha) * base_scores,
        threshold,
        margin_threshold,
        target_identities,
        distractor_identities,
    )


def run(args: argparse.Namespace) -> dict[str, Any]:
    if not torch.cuda.is_available() and args.device == "cuda":
        raise RuntimeError("CUDA is required")
    root = args.root.resolve()
    manifest = args.manifest.resolve()
    rows = load_rows(root, manifest)
    target_identities = parse_identity_list(args.target_identities, TARGET_IDENTITIES)
    distractor_identities = parse_identity_list(args.distractor_identities, DISTRACTOR_IDENTITIES)
    if set(target_identities) & set(distractor_identities):
        raise ValueError("target and distractor identity lists must be disjoint")
    eval_ids = set((*target_identities, *distractor_identities))
    train_rows = [row for row in rows if row["identityGroupId"] not in eval_ids]
    if len({row["identityGroupId"] for row in train_rows}) < 10:
        raise ValueError("identity-heldout training split has fewer than 10 identities")
    missing_gallery = [
        identity
        for identity in target_identities
        if not any(
            row["identityGroupId"] == identity and row["benchmarkRole"] == "gallery" for row in rows
        )
    ]
    missing_query = [
        identity
        for identity in (*target_identities, *distractor_identities)
        if not any(
            row["identityGroupId"] == identity and row["benchmarkRole"] == "query" for row in rows
        )
    ]
    if missing_gallery or missing_query:
        raise ValueError(
            f"incomplete held-out evaluation gallery={missing_gallery} query={missing_query}"
        )
    device = torch.device(args.device)
    processor = AutoProcessor.from_pretrained(args.checkpoint, local_files_only=True)
    model = CLIPModel.from_pretrained(args.checkpoint, local_files_only=True).to(device).eval()
    raw_clip = clip_features(rows, model, processor, device, args.batch_size)
    del model
    if device.type == "cuda":
        torch.cuda.empty_cache()
    teacher_raw = None
    if args.teacher_checkpoint:
        teacher_processor = AutoProcessor.from_pretrained(
            args.teacher_checkpoint, local_files_only=True
        )
        teacher_model = (
            CLIPModel.from_pretrained(args.teacher_checkpoint, local_files_only=True)
            .to(device)
            .eval()
        )
        teacher_raw = clip_features(rows, teacher_model, teacher_processor, device, args.batch_size)
        del teacher_model
        if device.type == "cuda":
            torch.cuda.empty_cache()
    raw_color = F.normalize(color_features([Path(str(row["_path"])) for row in rows]), dim=-1)
    fused = F.normalize(torch.cat((raw_clip, raw_color), dim=1), dim=-1)
    train_indices = [
        index for index, row in enumerate(rows) if row["identityGroupId"] not in eval_ids
    ]
    train_features = fused[train_indices]
    train_identity_values = sorted({rows[index]["identityGroupId"] for index in train_indices})
    train_label_map = {identity: index for index, identity in enumerate(train_identity_values)}
    train_labels = torch.tensor(
        [train_label_map[rows[index]["identityGroupId"]] for index in train_indices],
        dtype=torch.long,
    )
    adapter = train_adapter(
        train_features,
        train_labels,
        device,
        args.epochs,
        args.seed,
        args.objective,
        len(train_identity_values),
        teacher_features=teacher_raw[train_indices] if teacher_raw is not None else None,
    )
    with torch.inference_mode():
        adapted = adapter(fused.to(device)).cpu()
    thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
    baseline = {
        str(threshold): evaluate(
            rows,
            fused,
            threshold,
            args.gallery_aggregation,
            target_identities,
            distractor_identities,
            args.track_pooling,
        )
        for threshold in thresholds
    }
    learned = {
        str(threshold): evaluate(
            rows,
            adapted,
            threshold,
            args.gallery_aggregation,
            target_identities,
            distractor_identities,
            args.track_pooling,
        )
        for threshold in thresholds
    }
    fusion = {
        str(alpha): {
            str(threshold): evaluate_score_blend(
                rows,
                fused,
                adapted,
                alpha,
                threshold,
                args.gallery_aggregation,
                target_identities,
                distractor_identities,
                args.track_pooling,
            )
            for threshold in thresholds
        }
        for alpha in (0.25, 0.5, 0.75, 1.0)
    }
    margin_fusion = {
        str(alpha): {
            str(threshold): {
                str(margin): evaluate_score_blend_margin(
                    rows,
                    fused,
                    adapted,
                    alpha,
                    threshold,
                    margin,
                    args.gallery_aggregation,
                    target_identities,
                    distractor_identities,
                    args.track_pooling,
                )
                for margin in (0.0, 0.02, 0.05, 0.1, 0.15, 0.2)
            }
            for threshold in thresholds
        }
        for alpha in (0.25, 0.5, 0.75, 1.0)
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output.with_name(f"{args.output.stem}.adapter.pt")
    torch.save(
        {
            "state_dict": adapter.state_dict(),
            "inputDim": fused.shape[1],
            "targetIdentities": target_identities,
            "distractorIdentities": distractor_identities,
        },
        checkpoint,
    )
    result = {
        "schemaVersion": "cctv-chirla-reid-adapter-v1",
        "model": f"{args.checkpoint} plus spatial HSV adapter",
        "checkpoint": args.checkpoint,
        "device": str(device),
        "dataset": sorted({str(row.get("dataset", "unknown")) for row in rows}),
        "datasetStatus": "public-proxy-not-project-CCTV-review",
        "split": {
            "evaluationIdentities": sorted(eval_ids),
            "targetIdentities": list(target_identities),
            "distractorIdentities": list(distractor_identities),
            "trainIdentities": sorted({row["identityGroupId"] for row in train_rows}),
            "identityDisjoint": not bool(eval_ids & {row["identityGroupId"] for row in train_rows}),
            "galleryRole": "gallery",
            "queryRole": "query",
            "trackKey": "identityGroupId|sequenceId|cameraId|subset",
        },
        "counts": {
            "rows": len(rows),
            "trainRows": len(train_rows),
            "trainIdentities": len({row["identityGroupId"] for row in train_rows}),
        },
        "baseline": baseline,
        "learned": learned,
        "fusion": fusion,
        "marginFusion": margin_fusion,
        "metricUnit": "track",
        "thresholdSelection": "descriptive query-grid; never used for promotion",
        "promotionEligible": False,
        "promotionBlockers": [
            "datasetStatus=public-proxy-not-project-CCTV-review",
            "query-grid is descriptive only and cannot select a production threshold",
            "project-CCTV validation-only threshold selection is required",
        ],
        "checkpointPath": str(checkpoint),
        "manifestSha256": sha256_file(manifest),
        "seed": args.seed,
        "epochs": args.epochs,
        "objective": args.objective,
        "teacherCheckpoint": args.teacher_checkpoint,
        "galleryAggregation": args.gallery_aggregation,
        "trackPooling": args.track_pooling,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train an identity-disjoint CHIRLA ReID adapter")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--checkpoint", default="openai/clip-vit-large-patch14")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=160)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument(
        "--objective",
        choices=(
            "supcon",
            "supcon_ce",
            "supcon_ce_triplet",
            "supcon_ce_triplet_kd",
            "supcon_arcface_triplet",
            "supcon_arcface_triplet_kd",
            "supcon_cosface_triplet",
            "supcon_cosface_triplet_kd",
            "supcon_circle_triplet",
            "supcon_circle_triplet_kd",
        ),
        default="supcon_ce",
    )
    parser.add_argument("--teacher-checkpoint")
    parser.add_argument("--target-identities")
    parser.add_argument("--distractor-identities")
    parser.add_argument(
        "--gallery-aggregation",
        choices=("prototype", "max", "hybrid"),
        default="prototype",
    )
    parser.add_argument("--track-pooling", choices=("mean", "quality"), default="mean")
    args = parser.parse_args()
    print(json.dumps(run(args), ensure_ascii=False))


if __name__ == "__main__":
    main()
