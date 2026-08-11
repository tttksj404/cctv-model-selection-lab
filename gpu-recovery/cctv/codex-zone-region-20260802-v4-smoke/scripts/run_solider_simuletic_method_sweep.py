# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "numpy>=2.0",
#   "pillow>=10",
#   "pyarrow>=18",
#   "torch",
# ]
# ///
from __future__ import annotations

import argparse
import copy
import json
import platform
import random
from pathlib import Path
from typing import Any

import numpy as np
import torch
from torch import Tensor, nn
from torch.nn import functional as F

from run_solider_pa100k_parquet import (
    ATTRIBUTES, _extract_split, _hash_file, _metrics, _official_bce_loss,
)
from solider_simuletic_sweep_data import (
    ExperimentRuntimeError, feature_rows, group_metrics, group_split, load_simuletic, load_sonnet, masked_metrics, sha256_file,
)


def _masked_bce(logits: Tensor, targets: Tensor, mask: Tensor, ratio: Tensor) -> Tensor:
    weights = torch.exp(targets * (1 - ratio) + (1 - targets) * ratio)
    values = F.binary_cross_entropy_with_logits(logits, targets, reduction="none")
    valid = mask.to(dtype=values.dtype)
    return (values * weights * valid).sum() / valid.sum().clamp_min(1.0)


def _asl_loss(logits: Tensor, targets: Tensor, mask: Tensor) -> Tensor:
    probabilities = logits.sigmoid()
    positive = probabilities
    negative = (1.0 - probabilities + 0.05).clamp(max=1.0)
    log_probability = targets * torch.log(positive.clamp_min(1e-8)) + (1 - targets) * torch.log(negative.clamp_min(1e-8))
    probability = positive * targets + negative * (1 - targets)
    gamma = 1.0 * targets + 4.0 * (1 - targets)
    values = -log_probability * (1 - probability).pow(gamma) * mask
    return values.sum() / mask.to(dtype=values.dtype).sum().clamp_min(1.0)


def _label_transition(labels: Tensor) -> Tensor:
    positives = labels.to(dtype=torch.float32)
    cooccurrence = positives.T @ positives
    cooccurrence.fill_diagonal_(0.0)
    cooccurrence = cooccurrence + torch.eye(cooccurrence.shape[0], device=cooccurrence.device)
    return cooccurrence / cooccurrence.sum(dim=1, keepdim=True).clamp_min(1e-6)


def _graph_regularized_asl(
    logits: Tensor,
    targets: Tensor,
    mask: Tensor,
    transition: Tensor,
) -> Tensor:
    base = _asl_loss(logits, targets, mask)
    probabilities = logits.sigmoid()
    propagated = (targets @ transition).clamp(0.0, 1.0)
    graph_values = (probabilities - propagated).pow(2) * mask
    graph = graph_values.sum() / mask.to(dtype=graph_values.dtype).sum().clamp_min(1.0)
    return base + 0.05 * graph


def _load_head(path: Path, feature_count: int, device: torch.device) -> nn.Linear:
    payload = torch.load(path.resolve(), map_location="cpu", weights_only=True)
    if not isinstance(payload, dict) or not isinstance(payload.get("state_dict"), dict):
        raise ExperimentRuntimeError("invalid base head checkpoint")
    if tuple(payload.get("attributes", ())) != ATTRIBUTES:
        raise ExperimentRuntimeError("base head ontology does not match PA-100K")
    head = nn.Linear(feature_count, len(ATTRIBUTES))
    head.load_state_dict(payload["state_dict"])
    return head.to(device).eval()


def _load_backbone(vendor_root: Path, checkpoint: Path) -> nn.Module:
    from run_solider_proxy_experiment import _load_backbone as load_vendor_backbone

    return load_vendor_backbone(vendor_root, checkpoint)


def _train_pa_head(features: Tensor, labels: Tensor, device: torch.device) -> nn.Linear:
    head = nn.Linear(features.shape[1], labels.shape[1]).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.001, weight_decay=0.0001)
    ratio = labels.mean(dim=0)
    for _ in range(5):
        order = torch.randperm(features.shape[0])
        for start in range(0, len(order), 2048):
            batch = order[start : start + 2048]
            loss = _official_bce_loss(head(features[batch].to(device)), labels[batch].to(device), ratio)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def _train_mixed(
    initial: nn.Linear,
    pa_features: Tensor,
    pa_labels: Tensor,
    simu_features: Tensor,
    simu_labels: Tensor,
    simu_masks: Tensor,
    device: torch.device,
    method: str,
    epochs: int,
    simu_repeat: int,
    sonnet: tuple[Tensor, Tensor, Tensor, Tensor] | None,
    transition: Tensor,
) -> nn.Linear:
    head = copy.deepcopy(initial).to(device)
    features: list[Tensor] = [pa_features, simu_features.repeat((simu_repeat, 1))]
    labels: list[Tensor] = [pa_labels, simu_labels.repeat((simu_repeat, 1))]
    masks: list[Tensor] = [torch.ones_like(pa_labels), simu_masks.repeat((simu_repeat, 1))]
    source: list[Tensor] = [torch.zeros(len(pa_features), dtype=torch.long), torch.ones(len(simu_features) * simu_repeat, dtype=torch.long)]
    if sonnet is not None:
        teacher_features, teacher_labels, teacher_masks, _teacher_weights = sonnet
        features.append(teacher_features.repeat((4, 1)))
        labels.append(teacher_labels.repeat((4, 1)))
        masks.append(teacher_masks.repeat((4, 1)))
        source.append(torch.full((len(teacher_features) * 4,), 2, dtype=torch.long))
    all_features = torch.cat(features)
    all_labels = torch.cat(labels)
    all_masks = torch.cat(masks)
    all_source = torch.cat(source)
    ratio = pa_labels.mean(dim=0).to(device)
    optimizer = torch.optim.AdamW(head.parameters(), lr=0.0002, weight_decay=0.0001)
    for _ in range(epochs):
        order = torch.randperm(len(all_features))
        for start in range(0, len(order), 2048):
            batch = order[start : start + 2048]
            logits = head(all_features[batch].to(device))
            targets = all_labels[batch].to(device)
            valid = all_masks[batch].to(device)
            kinds = all_source[batch]
            losses: list[Tensor] = []
            for kind in (0, 1, 2):
                selected = kinds == kind
                if not bool(selected.any()):
                    continue
                selected_logits = logits[selected]
                selected_targets = targets[selected]
                selected_mask = valid[selected]
                if kind == 0:
                    value = _official_bce_loss(selected_logits, selected_targets, ratio)
                elif method == "mixed_asl_graph":
                    value = _graph_regularized_asl(selected_logits, selected_targets, selected_mask, transition)
                elif method in {"mixed_asl", "mixed_asl_sonnet"}:
                    value = _asl_loss(selected_logits, selected_targets, selected_mask)
                else:
                    value = _masked_bce(selected_logits, selected_targets, selected_mask, ratio)
                losses.append(value * (0.01 if kind == 2 else 1.0))
            loss = torch.stack(losses).sum()
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    return head.eval()


def _evaluate(
    head: nn.Module,
    pa_val_features: Tensor,
    pa_val_labels: Tensor,
    pa_test_features: Tensor,
    pa_test_labels: Tensor,
    simu_features: Tensor,
    simu_rows: tuple[dict[str, Any], ...],
    test_indices: tuple[int, ...],
    device: torch.device,
) -> dict[str, Any]:
    with torch.inference_mode():
        pa_val_logits = head(pa_val_features.to(device)).float().cpu()
        pa_test_logits = head(pa_test_features.to(device)).float().cpu()
        simu_logits = head(simu_features.to(device)).float().cpu()
    simu_labels = torch.stack([row["labels"] for row in simu_rows])
    simu_masks = torch.stack([row["mask"] for row in simu_rows])
    heldout = list(test_indices)
    return {
        "pa100k": {"val": _metrics(pa_val_logits, pa_val_labels), "test": _metrics(pa_test_logits, pa_test_labels)},
        "simuletic": {
            "all": masked_metrics(simu_logits, simu_labels, simu_masks),
            "image_heldout": masked_metrics(simu_logits[heldout], simu_labels[heldout], simu_masks[heldout]),
            "group_heldout": group_metrics(simu_logits, simu_rows, test_indices),
        },
    }


def run(args: argparse.Namespace) -> None:
    if not torch.cuda.is_available():
        raise ExperimentRuntimeError("CUDA is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    device = torch.device("cuda")
    workspace = Path.cwd().resolve()
    checkpoint = args.checkpoint.resolve()
    rows = load_simuletic(args.simu_root.resolve(), args.simu_metadata.resolve())
    identities = sorted({int(row["identity"]) for row in rows})
    train_ids, val_ids, test_ids = group_split(rows)
    if not train_ids or not val_ids or not test_ids:
        raise ExperimentRuntimeError("Simuletic group split is empty")
    train_indices = tuple(index for index, row in enumerate(rows) if row["identity"] in train_ids)
    test_indices = tuple(index for index, row in enumerate(rows) if row["identity"] in test_ids)
    backbone = _load_backbone(args.vendor_root.resolve(), checkpoint).to(device)
    backbone.eval()
    pa_train_features, pa_train_labels = _extract_split(args.data_root.resolve() / "train.parquet", backbone, device, args.extract_batch_size, args.pa_train_rows)
    pa_val_features, pa_val_labels = _extract_split(args.data_root.resolve() / "val.parquet", backbone, device, args.extract_batch_size, args.pa_val_rows)
    pa_test_features, pa_test_labels = _extract_split(args.data_root.resolve() / "test.parquet", backbone, device, args.extract_batch_size, args.pa_test_rows)
    simu_features = feature_rows(backbone, rows, device, args.extract_batch_size)
    simu_labels = torch.stack([row["labels"] for row in rows])
    simu_masks = torch.stack([row["mask"] for row in rows])
    transition = _label_transition(pa_train_labels).to(device)
    sonnet = load_sonnet(args.sonnet_result.resolve(), args.sonnet_image_root.resolve(), backbone, device)
    base = _load_head(args.base_head, pa_train_features.shape[1], device) if args.base_head.is_file() else _train_pa_head(pa_train_features, pa_train_labels, device)
    train_features = simu_features[list(train_indices)]
    train_labels = simu_labels[list(train_indices)]
    train_masks = simu_masks[list(train_indices)]
    methods: dict[str, nn.Module] = {
        "base_pa_head": base,
        "mixed_weighted_bce": _train_mixed(base, pa_train_features, pa_train_labels, train_features, train_labels, train_masks, device, "mixed_weighted_bce", args.epochs, args.simu_repeat, None, transition),
        "mixed_asl": _train_mixed(base, pa_train_features, pa_train_labels, train_features, train_labels, train_masks, device, "mixed_asl", args.epochs, args.simu_repeat, None, transition),
        "mixed_asl_graph": _train_mixed(base, pa_train_features, pa_train_labels, train_features, train_labels, train_masks, device, "mixed_asl_graph", args.epochs, args.simu_repeat, None, transition),
        "mixed_asl_sonnet": _train_mixed(base, pa_train_features, pa_train_labels, train_features, train_labels, train_masks, device, "mixed_asl_sonnet", args.epochs, args.simu_repeat, sonnet, transition),
    }
    results: dict[str, Any] = {
        "status": "measured",
        "model": "SOLIDER Swin-B frozen backbone plus 26-attribute head",
        "data": {"pa100k": {"train": len(pa_train_labels), "val": len(pa_val_labels), "test": len(pa_test_labels)}, "simuletic": {"rows": len(rows), "groups": len(identities), "train_rows": len(train_indices), "test_rows": len(test_indices), "train_groups": sorted(train_ids), "val_groups": sorted(val_ids), "test_groups": sorted(test_ids), "mapped_label_count": int(simu_masks.sum())}, "split": "Simuletic identities sorted and split 60% train, 20% validation, 20% group-heldout test; PA-100K official split untouched"},
        "methods_definition": {"base_pa_head": "saved PA-100K weighted-BCE head", "mixed_weighted_bce": "PA-100K weighted BCE plus masked Simuletic BCE", "mixed_asl": "PA-100K weighted BCE plus masked Simuletic Asymmetric Loss gamma_neg=4 gamma_pos=1 clip=0.05", "mixed_asl_graph": "mixed_asl plus 0.05 co-occurrence-graph consistency from PA-100K train labels; ML-GCN-inspired ablation, not full ML-GCN", "mixed_asl_sonnet": "mixed_asl plus 0.01 response-level Sonnet auxiliary BCE; not logit KD"},
        "runtime": {"device": torch.cuda.get_device_name(0), "torch": torch.__version__, "python": platform.python_version(), "seed": args.seed, "epochs": args.epochs, "simu_repeat": args.simu_repeat},
        "provenance": {"script_sha256": sha256_file(Path(__file__).resolve()), "solider_checkpoint_sha256": _hash_file(checkpoint), "base_head_sha256": _hash_file(args.base_head) if args.base_head.is_file() else None, "simu_metadata_sha256": sha256_file(args.simu_metadata.resolve())},
        "metric_warning": "Simuletic is a synthetic CCTV attribute proxy; it is not project identity/track-heldout CCTV evidence. Unmapped color/hair fields are not part of the 26-label score.",
        "methods": {},
    }
    for name, head in methods.items():
        results["methods"][name] = _evaluate(head, pa_val_features, pa_val_labels, pa_test_features, pa_test_labels, simu_features, rows, test_indices, device)
        checkpoint_path = (workspace / "experiments/models" / f"solider_simuletic_{name}.pt").resolve()
        torch.save({"state_dict": head.state_dict(), "attributes": list(ATTRIBUTES), "method": name, "provenance": results["provenance"]}, checkpoint_path)
        results["methods"][name]["checkpoint"] = str(checkpoint_path)
        results["methods"][name]["checkpoint_sha256"] = _hash_file(checkpoint_path)
    output = args.output.resolve()
    if workspace not in output.parents:
        raise ExperimentRuntimeError("output must stay inside workspace")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "simuletic": {name: value["simuletic"] for name, value in results["methods"].items()}}, ensure_ascii=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("experiments/data/pa100k_full"))
    parser.add_argument("--checkpoint", type=Path, default=Path("experiments/models/solider_swin_base.pth"))
    parser.add_argument("--vendor-root", type=Path, default=Path("experiments/vendor/SOLIDER-PersonAttributeRecognition"))
    parser.add_argument("--base-head", type=Path, default=Path("experiments/models/solider-pa100k-weighted-full-head-remote.pt"))
    parser.add_argument("--simu-root", type=Path, default=Path("experiments/data/cctv_proxy/simuletic_expanded"))
    parser.add_argument("--simu-metadata", type=Path, default=Path("experiments/data/cctv_proxy/simuletic_expanded/metadata.jsonl"))
    parser.add_argument("--sonnet-result", type=Path, default=Path("experiments/results/sonnet_cli_pilot.json"))
    parser.add_argument("--sonnet-image-root", type=Path, default=Path("experiments/data/cctv_proxy/person_only/simuletic"))
    parser.add_argument("--output", type=Path, default=Path("experiments/results/solider_simuletic_method_sweep.json"))
    parser.add_argument("--pa-train-rows", type=int, default=80000)
    parser.add_argument("--pa-val-rows", type=int, default=10000)
    parser.add_argument("--pa-test-rows", type=int, default=10000)
    parser.add_argument("--extract-batch-size", type=int, default=16)
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--simu-repeat", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260727)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
