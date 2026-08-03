import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torchreid
from PIL import Image
from torch import Tensor, nn
from torch.nn import functional as F
from torchvision.transforms import Compose, Normalize, RandomHorizontalFlip, Resize, ToTensor

TARGET_IDENTITIES = ("1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14")
DISTRACTOR_IDENTITIES = ("-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(root: Path, manifest: Path) -> list[dict[str, Any]]:
    rows = []
    for line in manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row["identityGroupId"] = str(row["identityGroupId"])
        row["_path"] = str(root / str(row["localPath"]))
        if not Path(row["_path"]).is_file():
            raise FileNotFoundError(row["_path"])
        rows.append(row)
    return rows


def track_key(row: dict[str, Any]) -> str:
    return "|".join(
        str(row.get(key, "")) for key in ("identityGroupId", "sequenceId", "cameraId", "subset")
    )


def track_vectors(
    rows: list[dict[str, Any]], features: Tensor
) -> tuple[list[dict[str, Any]], Tensor]:
    groups: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        groups[track_key(row)].append(index)
    output_rows = []
    output_vectors = []
    for key, indices in sorted(groups.items()):
        row = dict(rows[indices[0]])
        row["trackKey"] = key
        row["frameCount"] = len(indices)
        output_rows.append(row)
        output_vectors.append(F.normalize(features[indices].mean(dim=0), dim=0))
    return output_rows, torch.stack(output_vectors)


def encode(
    rows: list[dict[str, Any]],
    model: nn.Module,
    transform: Compose,
    device: torch.device,
    batch_size: int,
) -> Tensor:
    chunks = []
    model.eval()
    with torch.inference_mode():
        for start in range(0, len(rows), batch_size):
            images = []
            for row in rows[start : start + batch_size]:
                with Image.open(row["_path"]) as image:
                    images.append(transform(image.convert("RGB")))
            features = model(torch.stack(images).to(device))
            chunks.append(F.normalize(features.float(), dim=-1).cpu())
    return torch.cat(chunks)


def evaluate(
    rows: list[dict[str, Any]], features: Tensor, threshold: float, aggregation: str
) -> dict[str, Any]:
    gallery_indices = [
        index
        for index, row in enumerate(rows)
        if row.get("benchmarkRole") == "gallery" and row["identityGroupId"] in TARGET_IDENTITIES
    ]
    query_indices = [
        index
        for index, row in enumerate(rows)
        if row.get("benchmarkRole") == "query"
        and row["identityGroupId"] in (*TARGET_IDENTITIES, *DISTRACTOR_IDENTITIES)
    ]
    gallery_rows, gallery_features = track_vectors(
        [rows[index] for index in gallery_indices], features[gallery_indices]
    )
    query_rows, query_features = track_vectors(
        [rows[index] for index in query_indices], features[query_indices]
    )
    columns = []
    for identity in TARGET_IDENTITIES:
        indices = [
            index for index, row in enumerate(gallery_rows) if row["identityGroupId"] == identity
        ]
        identity_scores = query_features @ gallery_features[indices].T
        if aggregation == "max":
            columns.append(identity_scores.max(dim=1).values)
        else:
            columns.append(identity_scores.mean(dim=1))
    scores = torch.stack(columns, dim=1)
    identities = list(TARGET_IDENTITIES)
    target_indices = [
        index for index, row in enumerate(query_rows) if row["identityGroupId"] in TARGET_IDENTITIES
    ]
    distractor_indices = [
        index
        for index, row in enumerate(query_rows)
        if row["identityGroupId"] in DISTRACTOR_IDENTITIES
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
    distractor_scores = scores[distractor_indices].max(dim=1).values
    return {
        "galleryTrackCount": len(gallery_rows),
        "queryTrackCount": len(query_rows),
        "targetQueryTrackCount": len(target_indices),
        "distractorQueryTrackCount": len(distractor_indices),
        "rank1": float(np.mean(np.asarray(ranks) == 1)),
        "recallAt5": float(np.mean(np.asarray(ranks) <= 5)),
        "falseMatchRate": float((distractor_scores >= threshold).float().mean()),
        "falseRejectRate": float(
            (scores[target_indices].max(dim=1).values < threshold).float().mean()
        ),
        "threshold": threshold,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    root = args.root.resolve()
    manifest = args.manifest.resolve()
    rows = load_rows(root, manifest)
    evaluation_ids = set((*TARGET_IDENTITIES, *DISTRACTOR_IDENTITIES))
    train_rows = [row for row in rows if row["identityGroupId"] not in evaluation_ids]
    train_identities = sorted({row["identityGroupId"] for row in train_rows})
    if len(train_identities) < 10:
        raise ValueError("identity-heldout training split has fewer than 10 identities")
    label_map = {identity: index for index, identity in enumerate(train_identities)}
    device = torch.device(args.device)
    train_transform = Compose(
        [
            Resize((256, 128)),
            RandomHorizontalFlip(p=0.5),
            ToTensor(),
            Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    eval_transform = Compose(
        [
            Resize((256, 128)),
            ToTensor(),
            Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
        ]
    )
    model = torchreid.models.build_model(
        name="osnet_x1_0", num_classes=len(train_identities), pretrained=True, loss="softmax"
    ).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate, weight_decay=0.0005)
    labels = torch.tensor(
        [label_map[row["identityGroupId"]] for row in train_rows], dtype=torch.long
    )
    model.train()
    for _ in range(args.epochs):
        permutation = torch.randperm(len(train_rows))
        for start in range(0, len(train_rows), args.batch_size):
            indices = permutation[start : start + args.batch_size].tolist()
            images = []
            for index in indices:
                with Image.open(train_rows[index]["_path"]) as image:
                    images.append(train_transform(image.convert("RGB")))
            logits = model(torch.stack(images).to(device))
            loss = F.cross_entropy(logits, labels[indices].to(device))
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
    features = encode(rows, model, eval_transform, device, args.batch_size)
    thresholds = [0.5, 0.6, 0.7, 0.8, 0.9]
    results = {
        aggregation: {
            str(threshold): evaluate(rows, features, threshold, aggregation)
            for threshold in thresholds
        }
        for aggregation in ("mean", "max")
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = args.output.with_suffix(".pt")
    torch.save(
        {
            "state_dict": model.state_dict(),
            "trainIdentities": train_identities,
            "evaluationIdentities": sorted(evaluation_ids),
        },
        checkpoint,
    )
    result = {
        "schemaVersion": "market1501-osnet-finetune-v1",
        "model": "OSNet x1.0 ImageNet pretrained plus identity-heldout fine-tuning",
        "device": str(device),
        "dataset": "Market1501-attributes",
        "datasetStatus": "public-proxy-not-project-CCTV-review",
        "split": {
            "evaluationIdentities": sorted(evaluation_ids),
            "trainIdentities": train_identities,
            "identityDisjoint": not bool(evaluation_ids & set(train_identities)),
            "galleryRole": "gallery",
            "queryRole": "query",
        },
        "counts": {
            "rows": len(rows),
            "trainRows": len(train_rows),
            "trainIdentities": len(train_identities),
        },
        "results": results,
        "promotionEligible": any(
            value["rank1"] >= 0.85
            and value["recallAt5"] >= 0.95
            and value["falseMatchRate"] <= 0.05
            and value["falseRejectRate"] <= 0.15
            for aggregation_values in results.values()
            for value in aggregation_values.values()
        ),
        "checkpointPath": str(checkpoint),
        "manifestSha256": sha256_file(manifest),
        "epochs": args.epochs,
        "learningRate": args.learning_rate,
        "seed": args.seed,
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", choices=("cuda", "cpu"), default="cuda")
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=60)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()
    run(args)


if __name__ == "__main__":
    main()
