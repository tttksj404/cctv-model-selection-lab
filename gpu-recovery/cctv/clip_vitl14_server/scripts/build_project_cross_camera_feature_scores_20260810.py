from __future__ import annotations

import argparse
import gc
import json
import sys
from collections.abc import Sequence
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark_chirla_reid import (  # noqa: E402
    ImageEncoder,
    Record,
    _aggregate_identity_scores,
    _load_records,
)


def split_records(records: Sequence[Record]) -> tuple[list[Record], list[Record], list[str]]:
    gallery = [record for record in records if record.role == "gallery"]
    queries = [record for record in records if record.role == "query"]
    identities = sorted({record.identity for record in queries} & {record.identity for record in gallery})
    if len(identities) < 4:
        raise ValueError(f"strict project gate requires at least 4 identities, found {len(identities)}")
    gallery = [record for record in gallery if record.identity in identities]
    queries = [record for record in queries if record.identity in identities]
    for query in queries:
        if not any(
            gallery_row.identity == query.identity
            and gallery_row.camera != query.camera
            and gallery_row.sequence != query.sequence
            for gallery_row in gallery
        ):
            raise ValueError(f"query has no strict cross-camera/sequence gallery: {query.path}")
    return gallery, queries, identities


def score_model(
    model_name: str,
    gallery: list[Record],
    queries: list[Record],
    identities: list[str],
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
    gallery_indices = {
        identity: [index for index, record in enumerate(gallery) if record.identity == identity]
        for identity in identities
    }
    scores = _aggregate_identity_scores(
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
    del encoder, gallery_features, query_features
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return scores


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--solider-checkpoint", type=Path, required=True)
    parser.add_argument("--solider-root", type=Path, required=True)
    args = parser.parse_args()
    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")

    records = _load_records(args.root, args.manifest)
    gallery, queries, identities = split_records(records)
    models = [
        "solider-reid-swin-base-msmt17",
        "siglip2-base",
        "dinov2-base",
        "clip-vit-l14",
    ]
    scores: dict[str, np.ndarray] = {}
    for model_name in models:
        print(f"encoding {model_name}", flush=True)
        scores[model_name] = score_model(model_name, gallery, queries, identities, args)
        print(f"scored {model_name} shape={scores[model_name].shape}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        solider_reid_swin_base_msmt17=scores["solider-reid-swin-base-msmt17"],
        siglip2_base=scores["siglip2-base"],
        dinov2_base=scores["dinov2-base"],
        clip_vit_l14=scores["clip-vit-l14"],
    )
    metadata = {
        "schemaVersion": "project-cctv-cross-camera-score-matrix-v1",
        "dataset": "EyesOnU project CCTV",
        "datasetStatus": "project-CCTV-manually-adjudicated-cross-video",
        "protocol": "strict-cross-camera-sequence",
        "aggregation": "mean gallery identity score; mean query score at track gate",
        "tta": "hflip",
        "identities": identities,
        "queryIdentity": [record.identity for record in queries],
        "queryPath": [str(record.path) for record in queries],
        "queryCamera": [record.camera for record in queries],
        "querySequence": [record.sequence for record in queries],
        "galleryCount": len(gallery),
        "queryCount": len(queries),
        "scoreNpz": str(args.output),
        "secondAdjudicatorRequired": True,
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
