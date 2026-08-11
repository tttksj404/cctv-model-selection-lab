from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark_chirla_reid import ImageEncoder, Record, _load_records  # noqa: E402


def split_records(records: list[Record]) -> tuple[list[Record], list[Record], list[str]]:
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
    encoder = ImageEncoder(
        model_name="solider-reid-swin-base-msmt17",
        device=torch.device(args.device),
        checkpoint_override=str(args.solider_checkpoint),
        solider_root=args.solider_root,
        tta="hflip",
    )
    gallery_features = encoder.encode(gallery, args.batch_size)
    query_features = encoder.encode(queries, args.batch_size)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.output,
        gallery_features=np.asarray(gallery_features, dtype=np.float32),
        query_features=np.asarray(query_features, dtype=np.float32),
    )
    metadata = {
        "schemaVersion": "project-cctv-cross-camera-solider-embeddings-v1",
        "dataset": "EyesOnU project CCTV",
        "protocol": "strict-cross-camera-sequence",
        "identities": identities,
        "galleryIdentity": [record.identity for record in gallery],
        "galleryTrack": [record.path.parent.name for record in gallery],
        "galleryCamera": [record.camera for record in gallery],
        "gallerySequence": [record.sequence for record in gallery],
        "queryIdentity": [record.identity for record in queries],
        "queryTrack": [record.path.parent.name for record in queries],
        "queryCamera": [record.camera for record in queries],
        "querySequence": [record.sequence for record in queries],
        "galleryCount": len(gallery),
        "queryCount": len(queries),
        "tta": "hflip",
    }
    args.output.with_suffix(".json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
