from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import cast

from scripts.prid2011_track_cache import save_track_cache
from scripts.prid2011_track_metrics import (
    calibrate_open_set,
    evaluate_retrieval,
    pool_tracks,
)


def _text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be non-empty text")
    return value


def _load_rows(root: Path, manifest: Path) -> list[dict[str, object]]:
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    for row in rows:
        image = root / _text(row, "localPath")
        if not image.is_file():
            raise FileNotFoundError(image)
        actual = hashlib.sha256(image.read_bytes()).hexdigest()
        if actual != _text(row, "sha256"):
            raise ValueError(f"sha256 mismatch: {image}")
    return rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate frame encoders on strict PRID2011 track retrieval"
    )
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--checkpoint")
    parser.add_argument("--solider-root", type=Path)
    parser.add_argument("--fastreid-root", type=Path)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--tta", choices=("none", "hflip"), default="hflip")
    parser.add_argument("--track-cache-output", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    from scripts.benchmark_chirla_reid import ImageEncoder, Record

    args = _parse_args()
    torch_module = importlib.import_module("torch")
    device_factory = cast(
        Callable[[str], object],
        vars(torch_module)["device"],
    )
    rows = _load_rows(args.root, args.manifest)
    encoder_records = [
        Record(
            path=args.root / _text(row, "localPath"),
            identity=_text(row, "identityGroupId"),
            role=_text(row, "benchmarkRole"),
            camera=_text(row, "cameraId"),
            sequence=_text(row, "sequenceId"),
            sha256=_text(row, "sha256"),
        )
        for row in rows
    ]
    encoder = ImageEncoder(
        args.model,
        device_factory(args.device),
        checkpoint_override=args.checkpoint,
        fastreid_root=args.fastreid_root,
        solider_root=args.solider_root,
        tta=args.tta,
    )
    frame_embeddings = encoder.encode(encoder_records, args.batch_size)
    tracks = pool_tracks(rows, frame_embeddings)
    if args.track_cache_output is not None:
        save_track_cache(args.track_cache_output, tracks)
    validation = [track for track in tracks if track.split == "validation"]
    test = [track for track in tracks if track.split == "test"]
    calibration = calibrate_open_set(validation)
    result = {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "model": args.model,
        "checkpoint": encoder.checkpoint,
        "device": args.device,
        "tta": args.tta,
        "manifestSha256": hashlib.sha256(args.manifest.read_bytes()).hexdigest(),
        "trackCounts": {
            "validation": len(validation),
            "test": len(test),
        },
        "calibration": asdict(calibration),
        "validationMetrics": asdict(evaluate_retrieval(validation, calibration)),
        "testMetrics": asdict(evaluate_retrieval(test, calibration)),
        "promotionContract": {
            "identityDisjoint": True,
            "crossCamera": True,
            "thresholdSelectedOnValidationOnly": True,
            "sealedTest": True,
            "projectCctvEvidence": False,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps(result["testMetrics"], sort_keys=True))


if __name__ == "__main__":
    main()
