from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

import torch
import torch.nn.functional as F
from PIL import Image
from torch import nn
from transformers import CLIPModel, CLIPProcessor

ATTRS = (
    "clothing_color",
    "upper_color",
    "lower_color",
    "gender_presentation",
    "bag_present",
    "hat_present",
    "sleeve_length",
    "texture",
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def resolve_rows(root: Path, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for row in rows:
        local_path = Path(str(row.get("localPath") or row.get("path") or ""))
        candidates = [local_path, root / local_path]
        path = next((item for item in candidates if item.is_file()), None)
        if path is None:
            raise FileNotFoundError(f"missing image for {row.get('localPath')}")
        item = dict(row)
        item["_path"] = str(path)
        item["identityGroupId"] = str(item["identityGroupId"])
        item["benchmarkRole"] = str(item.get("benchmarkRole") or item.get("role") or "")
        resolved.append(item)
    return resolved


def image_batch(rows: list[dict[str, Any]]) -> list[Image.Image]:
    images: list[Image.Image] = []
    for row in rows:
        with Image.open(row["_path"]) as image:
            images.append(image.convert("RGB"))
    return images


def clip_features(
    model: CLIPModel,
    processor: CLIPProcessor,
    rows: list[dict[str, Any]],
    device: torch.device,
) -> torch.Tensor:
    inputs = processor(images=image_batch(rows), return_tensors="pt")
    pixel_values = inputs["pixel_values"].to(device)
    pooled = model.vision_model(pixel_values=pixel_values).pooler_output
    return F.normalize(model.visual_projection(pooled).float(), dim=1)


def supervised_contrastive(features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
    if features.shape[0] < 2:
        return features.sum() * 0.0
    logits = features @ features.T / 0.07
    diagonal = torch.eye(features.shape[0], dtype=torch.bool, device=features.device)
    positives = labels[:, None].eq(labels[None, :]) & ~diagonal
    logits = logits.masked_fill(diagonal, -torch.inf)
    log_prob = logits - torch.logsumexp(logits, dim=1, keepdim=True)
    valid = positives.any(dim=1)
    if not valid.any():
        return features.sum() * 0.0
    return -(log_prob.masked_fill(~positives, 0.0).sum(dim=1)[valid] / positives.sum(dim=1)[valid]).mean()


def batch_hard_triplet(features: torch.Tensor, labels: torch.Tensor) -> torch.Tensor:
    if features.shape[0] < 2:
        return features.sum() * 0.0
    distances = 1.0 - features @ features.T
    diagonal = torch.eye(features.shape[0], dtype=torch.bool, device=features.device)
    positives = labels[:, None].eq(labels[None, :]) & ~diagonal
    negatives = ~labels[:, None].eq(labels[None, :])
    valid = positives.any(dim=1) & negatives.any(dim=1)
    if not valid.any():
        return features.sum() * 0.0
    hardest_positive = distances.masked_fill(~positives, -torch.inf).max(dim=1).values
    hardest_negative = distances.masked_fill(~negatives, torch.inf).min(dim=1).values
    return F.relu(hardest_positive - hardest_negative + 0.2)[valid].mean()


def sonnet_loss(
    heads: nn.ModuleDict,
    features: torch.Tensor,
    batch_rows: list[dict[str, Any]],
    label_map: dict[str, dict[str, Any]],
    category_maps: dict[str, dict[str, int]],
) -> tuple[torch.Tensor, int]:
    losses: list[torch.Tensor] = []
    used = 0
    for attr in ATTRS:
        values: list[int] = []
        indices: list[int] = []
        mapping = category_maps[attr]
        for index, row in enumerate(batch_rows):
            label = label_map.get(Path(row["_path"]).name)
            if label is None or attr not in label or label[attr] is None:
                continue
            value = str(label[attr]).lower() if isinstance(label[attr], bool) else str(label[attr])
            if isinstance(label[attr], bool):
                value = "true" if label[attr] else "false"
            if value not in mapping:
                continue
            indices.append(index)
            values.append(mapping[value])
        if indices:
            logits = heads[attr](features[indices])
            target = torch.tensor(values, device=features.device, dtype=torch.long)
            losses.append(F.cross_entropy(logits, target))
            used += len(indices)
    if not losses:
        return features.sum() * 0.0, 0
    return torch.stack(losses).mean(), used


def build_categories(labels: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    categories: dict[str, dict[str, int]] = {}
    for attr in ATTRS:
        values: set[str] = set()
        for label in labels:
            value = label.get(attr)
            if isinstance(value, bool):
                value = "true" if value else "false"
            if value is not None:
                values.add(str(value).lower())
        categories[attr] = {value: index for index, value in enumerate(sorted(values))}
    return categories


def gallery_embeddings(rows: list[dict[str, Any]], features: torch.Tensor) -> tuple[list[str], torch.Tensor]:
    gallery_rows = [row for row in rows if row["benchmarkRole"] == "gallery"]
    identities = sorted({row["identityGroupId"] for row in gallery_rows}, key=lambda value: int(value))
    by_identity = {identity: [] for identity in identities}
    for index, row in enumerate(rows):
        if row["benchmarkRole"] == "gallery":
            by_identity[row["identityGroupId"]].append(index)
    vectors = [features[by_identity[identity]].mean(dim=0) for identity in identities]
    return identities, F.normalize(torch.stack(vectors), dim=1)


def score_split(
    rows: list[dict[str, Any]],
    features: torch.Tensor,
    threshold: float,
) -> dict[str, float | int]:
    identities, gallery = gallery_embeddings(rows, features)
    gallery_indices = {row["identityGroupId"]: [] for row in rows if row["benchmarkRole"] == "gallery"}
    for index, row in enumerate(rows):
        if row["benchmarkRole"] == "gallery":
            gallery_indices[row["identityGroupId"]].append(index)
    query_rows = [row for row in rows if row["benchmarkRole"] == "query"]
    query_indices = [index for index, row in enumerate(rows) if row["benchmarkRole"] == "query"]
    if not query_rows:
        raise ValueError("query rows are required")
    query = F.normalize(features[query_indices], dim=1)
    similarities = query @ gallery.T
    order = similarities.argsort(dim=1, descending=True)
    predicted = [identities[int(index)] for index in order[:, 0]]
    truth = [row["identityGroupId"] for row in query_rows]
    rank1 = sum(pred == target for pred, target in zip(predicted, truth)) / len(truth)
    recall5 = sum(target in [identities[int(index)] for index in row[:5]] for target, row in zip(truth, order)) / len(truth)
    target_scores = torch.tensor(
        [similarities[index, identities.index(target)].item() for index, target in enumerate(truth)]
    )
    top_scores = similarities[:, 0] if len(identities) == 1 else similarities.max(dim=1).values
    accepted = top_scores >= threshold
    false_reject = (target_scores < threshold).float().mean().item()
    wrong_accept = accepted & torch.tensor([pred != target for pred, target in zip(predicted, truth)])
    false_match = wrong_accept.float().mean().item()
    accepted_rank1 = sum(
        accepted[index].item() and predicted[index] == truth[index] for index in range(len(truth))
    ) / len(truth)
    return {
        "query_count": len(query_rows),
        "gallery_identity_count": len(identities),
        "rank1": rank1,
        "recall_at_5": recall5,
        "threshold": threshold,
        "false_match_rate": false_match,
        "false_reject_rate": false_reject,
        "accepted_rank1": accepted_rank1,
        "mean_target_score": target_scores.mean().item(),
        "mean_top_score": top_scores.mean().item(),
    }


def calibrate_threshold(rows: list[dict[str, Any]], features: torch.Tensor) -> float:
    identities, gallery = gallery_embeddings(rows, features)
    query_indices = [index for index, row in enumerate(rows) if row["benchmarkRole"] == "query"]
    query_rows = [row for row in rows if row["benchmarkRole"] == "query"]
    query = F.normalize(features[query_indices], dim=1)
    similarities = query @ gallery.T
    positive: list[float] = []
    impostor: list[float] = []
    for index, row in enumerate(query_rows):
        target = identities.index(row["identityGroupId"])
        positive.append(float(similarities[index, target]))
        impostor.extend(float(value) for j, value in enumerate(similarities[index]) if j != target)
    if not positive or not impostor:
        return 0.55
    positive_floor = sorted(positive)[max(0, int(len(positive) * 0.05) - 1)]
    impostor_ceiling = sorted(impostor)[min(len(impostor) - 1, int(len(impostor) * 0.95))]
    return float(max(0.0, min(0.99, (positive_floor + impostor_ceiling) / 2.0)))


def complete_evaluation_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    gallery_ids = {row["identityGroupId"] for row in rows if row["benchmarkRole"] == "gallery"}
    return [
        row
        for row in rows
        if row["identityGroupId"] in gallery_ids
        and row["benchmarkRole"] in {"gallery", "query"}
    ]


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for the requested remote training run")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    root = args.root.resolve()
    rows = resolve_rows(root, read_jsonl(root / args.manifest))
    identities = sorted(
        {row["identityGroupId"] for row in rows if row["benchmarkRole"] == "gallery"},
        key=lambda value: int(value),
    )
    holdout_ids = set(identities[::4])
    train_rows = [row for row in rows if row["identityGroupId"] not in holdout_ids]
    train_ids = sorted({row["identityGroupId"] for row in train_rows}, key=lambda value: int(value))
    calibration_id_values = [identity for identity in train_ids if identity in set(identities)]
    calibration_ids = set(calibration_id_values[::5])
    fit_rows = [row for row in train_rows if row["identityGroupId"] not in calibration_ids]
    calibration_rows = complete_evaluation_rows(
        [row for row in train_rows if row["identityGroupId"] in calibration_ids]
    )
    holdout_rows = [row for row in rows if row["identityGroupId"] in holdout_ids]

    label_rows = read_jsonl(root / args.sonnet_labels)
    label_map = {Path(str(label["sample_id"])).name: label for label in label_rows}
    categories = build_categories(label_rows)
    device = torch.device(args.device)
    processor = CLIPProcessor.from_pretrained(args.checkpoint, local_files_only=True)
    model = CLIPModel.from_pretrained(args.checkpoint, local_files_only=True).to(device)
    for parameter in model.parameters():
        parameter.requires_grad = False
    for layer in model.vision_model.encoder.layers[-2:]:
        for parameter in layer.parameters():
            parameter.requires_grad = True
    for parameter in model.visual_projection.parameters():
        parameter.requires_grad = True
    model.train()
    with torch.no_grad():
        feature_dim = clip_features(model, processor, fit_rows[:1], device).shape[1]
    fit_identity_values = [identity for identity in train_ids if identity not in calibration_ids]
    train_identity_map = {identity: index for index, identity in enumerate(fit_identity_values)}
    classifier = nn.Linear(feature_dim, len(train_identity_map)).to(device)
    heads = nn.ModuleDict(
        {attr: nn.Linear(feature_dim, len(categories[attr])) for attr in ATTRS if categories[attr]}
    ).to(device)
    parameters = [parameter for parameter in model.parameters() if parameter.requires_grad]
    parameters += list(classifier.parameters()) + list(heads.parameters())
    optimizer = torch.optim.AdamW(parameters, lr=args.learning_rate, weight_decay=0.01)
    for epoch in range(args.epochs):
        random.shuffle(fit_rows)
        epoch_loss = 0.0
        aux_used = 0
        steps = 0
        for start in range(0, len(fit_rows), args.batch_size):
            batch_rows = fit_rows[start : start + args.batch_size]
            if len(batch_rows) < 2:
                continue
            features = clip_features(model, processor, batch_rows, device)
            labels = torch.tensor(
                [train_identity_map[row["identityGroupId"]] for row in batch_rows],
                dtype=torch.long,
                device=device,
            )
            identity_loss = F.cross_entropy(classifier(features), labels)
            contrastive_loss = supervised_contrastive(features, labels)
            triplet_loss = batch_hard_triplet(features, labels)
            aux, used = sonnet_loss(heads, features, batch_rows, label_map, categories)
            loss = identity_loss + 0.20 * contrastive_loss + 0.20 * triplet_loss + 0.35 * aux
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(parameters, 1.0)
            optimizer.step()
            epoch_loss += float(loss.detach())
            aux_used += used
            steps += 1
        print(json.dumps({"epoch": epoch + 1, "loss": epoch_loss / max(steps, 1), "sonnet_aux_labels_used": aux_used}), flush=True)

    model.eval()
    with torch.inference_mode():
        all_features = torch.cat(
            [clip_features(model, processor, rows[start : start + args.eval_batch_size], device).cpu() for start in range(0, len(rows), args.eval_batch_size)]
        )
    threshold = calibrate_threshold(calibration_rows, all_features[[rows.index(row) for row in calibration_rows]])
    holdout_rows = complete_evaluation_rows(holdout_rows)
    holdout_result = score_split(holdout_rows, all_features[[rows.index(row) for row in holdout_rows]], threshold)
    fit_eval_rows = complete_evaluation_rows(fit_rows)
    fit_result = score_split(fit_eval_rows, all_features[[rows.index(row) for row in fit_eval_rows]], threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = args.output.with_suffix(".pt")
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "classifier_state_dict": classifier.state_dict(),
            "attribute_heads_state_dict": heads.state_dict(),
            "attribute_categories": categories,
            "teacher": "claude-sonnet-5",
            "teacher_label_type": "response-level categorical attributes; no logits/features",
        },
        checkpoint_path,
    )
    promotion = (
        holdout_result["rank1"] >= 0.85
        and holdout_result["recall_at_5"] >= 0.95
        and holdout_result["false_match_rate"] <= 0.05
        and holdout_result["false_reject_rate"] <= 0.15
    )
    result = {
        "schema_version": "cctv-clip-l14-sonnet-aux-v1",
        "method": "CLIP ViT-L/14 identity fine-tuning + CE/SupCon/batch-hard triplet + Sonnet 5 auxiliary attribute response distillation",
        "checkpoint": args.checkpoint,
        "device": str(device),
        "teacher": "claude-sonnet-5",
        "teacher_status": "sonnet5_oauth_cli_labels_uploaded",
        "teacher_label_type": "response-level categorical attributes; no logits/features",
        "dataset_status": "synthetic CCTV proxy; identity-heldout, not project CCTV",
        "split": {
            "identity_disjoint": not bool(holdout_ids & {row["identityGroupId"] for row in train_rows}),
            "fit_identities": len({row["identityGroupId"] for row in fit_rows}),
            "calibration_identities": len(calibration_ids),
            "holdout_identities": len(holdout_ids),
            "holdout_ids": sorted(holdout_ids, key=lambda value: int(value)),
        },
        "counts": {
            "manifest_rows": len(rows),
            "fit_rows": len(fit_rows),
            "calibration_rows": len(calibration_rows),
            "holdout_rows": len(holdout_rows),
            "sonnet_label_rows": len(label_rows),
            "sonnet_labels_used_in_fit": sum(Path(row["_path"]).name in label_map for row in fit_rows),
        },
        "metrics": holdout_result,
        "fit_metrics": fit_result,
        "calibration_threshold": threshold,
        "promotion": promotion,
        "checkpoint_path": str(checkpoint_path),
    }
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False), flush=True)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--manifest", type=Path, default=Path("synthetic_cctv_identity_manifest.jsonl"))
    parser.add_argument("--sonnet-labels", type=Path, default=Path("experiments/results/sonnet5_proxy_attribute_labels.jsonl"))
    parser.add_argument("--checkpoint", default="openai/clip-vit-large-patch14")
    parser.add_argument("--output", type=Path, default=Path("experiments/results/remote_clip_l14_sonnet_aux.json"))
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--eval-batch-size", type=int, default=64)
    parser.add_argument("--learning-rate", type=float, default=2e-6)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--seed", type=int, default=20260727)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())

