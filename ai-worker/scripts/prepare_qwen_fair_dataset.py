from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final

FIELDS: Final[tuple[str, ...]] = (
    "gender",
    "age",
    "viewpoint",
    "accessory",
    "sleeve",
    "bottom_type",
)
PROMPT: Final[str] = (
    "Analyze the person in this image. Return JSON only with exactly one "
    "attributes object and these six keys: gender, age, viewpoint, accessory, "
    "sleeve, bottom_type. Use the allowed labels from the dataset and do not "
    "add explanations."
)


def _int(labels: dict[str, object], key: str) -> int:
    value = labels.get(key, 0)
    return int(value) if isinstance(value, (int, float, str)) else 0


def _labels(labels: dict[str, object]) -> dict[str, str]:
    accessory = "none"
    for source, value in (
        ("HandBag", "handbag"),
        ("ShoulderBag", "shoulder_bag"),
        ("Backpack", "backpack"),
    ):
        if _int(labels, source) == 1:
            accessory = value
            break
    return {
        "gender": "female" if _int(labels, "Female") else "male",
        "age": (
            "elderly"
            if _int(labels, "AgeOver60")
            else "minor"
            if _int(labels, "AgeLess18")
            else "adult"
        ),
        "viewpoint": (
            "front" if _int(labels, "Front") else "side" if _int(labels, "Side") else "back"
        ),
        "accessory": accessory,
        "sleeve": (
            "short"
            if _int(labels, "ShortSleeve")
            else "long"
            if _int(labels, "LongSleeve")
            else "unknown"
        ),
        "bottom_type": (
            "trousers"
            if _int(labels, "Trousers")
            else "shorts"
            if _int(labels, "Shorts")
            else "skirt_dress"
            if _int(labels, "SkirtDress")
            else "unknown"
        ),
    }


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _split_key(seed: int, name: str) -> str:
    return hashlib.sha256(f"{seed}:{name}".encode()).hexdigest()


def _record(image_root: Path, name: str, labels: dict[str, str]) -> dict[str, object]:
    answer = json.dumps({"attributes": labels}, ensure_ascii=False, sort_keys=True)
    return {
        "messages": [
            {"role": "user", "content": f"<image>\n{PROMPT}"},
            {"role": "assistant", "content": answer},
        ],
        "images": [str((image_root / name).resolve())],
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path("experiments/data/cctv_proxy/pa100k/manifest.jsonl"),
    )
    parser.add_argument(
        "--image-root",
        type=Path,
        default=Path("experiments/data/cctv_proxy/pa100k"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("experiments/data/qwen_fair"),
    )
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--seed", type=int, default=20260722)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.limit < 12:
        raise SystemExit("--limit must be at least 12 for train/validation/test")
    source_rows = [
        json.loads(line)
        for line in args.source_manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ][: args.limit]
    rows: list[tuple[str, dict[str, str]]] = []
    for row in source_rows:
        name = row.get("image_name")
        labels = row.get("labels")
        if not isinstance(name, str) or not isinstance(labels, dict):
            raise SystemExit("manifest row must contain image_name and labels")
        image_root = args.image_root.resolve()
        image = (image_root / name).resolve()
        if image_root not in image.parents:
            raise SystemExit(f"image is outside image root: {name}")
        if not image.is_file():
            raise SystemExit(f"missing image: {image}")
        rows.append((name, _labels(labels)))
    if len(rows) != args.limit:
        raise SystemExit(f"expected {args.limit} rows, got {len(rows)}")

    rows.sort(key=lambda item: _split_key(args.seed, item[0]))
    train_end = max(1, int(len(rows) * 0.70))
    val_end = min(len(rows) - 1, train_end + max(1, int(len(rows) * 0.15)))
    partitions = {
        "train": rows[:train_end],
        "validation": rows[train_end:val_end],
        "test": rows[val_end:],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    files: dict[str, dict[str, object]] = {}
    for split, split_rows in partitions.items():
        output = args.output_dir / f"qwen_fair_{split}.jsonl"
        with output.open("w", encoding="utf-8", newline="\n") as stream:
            for name, labels in split_rows:
                stream.write(json.dumps(_record(args.image_root, name, labels), ensure_ascii=False))
                stream.write("\n")
        files[split] = {
            "path": str(output.resolve()),
            "rows": len(split_rows),
            "sha256": _digest(output),
            "image_names": [name for name, _ in split_rows],
        }
    metadata = {
        "schema": "qwen-fair-pa100k-v1",
        "proxyWarning": (
            "PA-100K labels do not measure CCTV identity, colour, texture, or track consistency."
        ),
        "sourceManifest": str(args.source_manifest.resolve()),
        "sourceManifestSha256": _digest(args.source_manifest),
        "imageRoot": str(args.image_root.resolve()),
        "limit": args.limit,
        "seed": args.seed,
        "fields": list(FIELDS),
        "prompt": PROMPT,
        "splitRatios": {"train": 0.70, "validation": 0.15, "test": 0.15},
        "files": files,
    }
    metadata_path = args.output_dir / "qwen_fair_manifest.json"
    metadata_path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "status": "valid",
                "output": str(metadata_path),
                "splits": {key: value["rows"] for key, value in files.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

