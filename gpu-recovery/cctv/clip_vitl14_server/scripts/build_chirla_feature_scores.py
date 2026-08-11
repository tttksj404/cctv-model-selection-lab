from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark_chirla_reid import (
    ImageEncoder,
    Record,
    _aggregate_identity_scores,  # pyright: ignore[reportPrivateUsage]
    _load_records,  # pyright: ignore[reportPrivateUsage]
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--solider-checkpoint", type=Path, required=True)
    parser.add_argument("--solider-root", type=Path, required=True)
    return parser.parse_args()


def _strict_split(records: Sequence[Record]) -> tuple[list[Record], list[Record], list[str]]:
    gallery = [record for record in records if record.role == "gallery"]
    queries = [record for record in records if record.role == "query"]
    gallery_by_identity: dict[str, list[Record]] = {}
    for record in gallery:
        gallery_by_identity.setdefault(record.identity, []).append(record)
    identities = sorted(
        {record.identity for record in queries} & set(gallery_by_identity)
    )
    if len(identities) < 10:
        raise ValueError(f"formal gate requires at least 10 identities, found {len(identities)}")
    selected_gallery = [
        record
        for identity in identities
        for record in gallery_by_identity[identity]
    ]
    queries = [record for record in queries if record.identity in identities]
    queries = [
        query
        for query in queries
        if any(
            record.identity == query.identity
            and record.camera != query.camera
            and record.sequence != query.sequence
            for record in selected_gallery
        )
    ]
    if not queries:
        raise ValueError("strict cross-camera/sequence protocol has no eligible queries")
    return selected_gallery, queries, identities


def _score_model(
    model_name: str,
    gallery: list[Record],
    queries: list[Record],
    identities: list[str],
    gallery_indices: dict[str, list[int]],
    args: argparse.Namespace,
) -> np.ndarray:
    checkpoint = None
    solider_root = None
    if model_name == "solider-reid-swin-base-msmt17":
        checkpoint = str(args.solider_checkpoint)
        solider_root = args.solider_root
    encoder = ImageEncoder(
        model_name=model_name,
        device=torch.device(args.device),
        checkpoint_override=checkpoint,
        solider_root=solider_root,
        tta="hflip",
    )
    gallery_features = encoder.encode(gallery, args.batch_size)
    query_features = encoder.encode(queries, args.batch_size)
    return _aggregate_identity_scores(
        query_features=query_features,
        gallery_features=gallery_features,
        queries=queries,
        gallery=gallery,
        identities=identities,
        gallery_indices=gallery_indices,
        gallery_aggregation="mean",
        gallery_topk=3,
        protocol="strict-cross-camera-sequence",
    )


def main() -> None:
    args = _parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required for this experiment")
    records = _load_records(args.root, args.manifest)
    gallery, queries, identities = _strict_split(records)
    gallery_indices = {
        identity: [
            index for index, record in enumerate(gallery) if record.identity == identity
        ]
        for identity in identities
    }
    model_names = [
        "solider-reid-swin-base-msmt17",
        "siglip2-base",
        "dinov2-base",
        "clip-vit-l14",
    ]
    scores: dict[str, np.ndarray] = {}
    for model_name in model_names:
        print(f"encoding {model_name}", flush=True)
        scores[model_name] = _score_model(
            model_name,
            gallery,
            queries,
            identities,
            gallery_indices,
            args,
        )
        print(f"scored {model_name} shape={scores[model_name].shape}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        solider_reid_swin_base_msmt17=scores["solider-reid-swin-base-msmt17"],
        siglip2_base=scores["siglip2-base"],
        dinov2_base=scores["dinov2-base"],
        clip_vit_l14=scores["clip-vit-l14"],
    )
    metadata: dict[str, object] = {
        "schema_version": "cctv-chirla-score-matrix-v1",
        "dataset_status": "public-proxy-not-project-CCTV-review",
        "protocol": "strict-cross-camera-sequence",
        "aggregation": "mean",
        "tta": "hflip",
        "identities": identities,
        "query_identity": [record.identity for record in queries],
        "query_path": [str(record.path) for record in queries],
        "query_camera": [record.camera for record in queries],
        "query_sequence": [record.sequence for record in queries],
        "gallery_count": len(gallery),
        "query_count": len(queries),
        "score_npz": str(args.output),
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps({"output": str(args.output), **metadata}, ensure_ascii=False))


if __name__ == "__main__":
    main()
