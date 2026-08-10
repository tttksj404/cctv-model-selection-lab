# ruff: noqa: E501

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import cast

import numpy as np
import torch
from PIL import Image
from torchvision.models.detection import (
    FasterRCNN_MobileNet_V3_Large_320_FPN_Weights,
    fasterrcnn_mobilenet_v3_large_320_fpn,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = PROJECT_ROOT / "experiments" / "data" / "cctv_proxy"
SOURCE_DATASETS = (SOURCE_ROOT / "simuletic", SOURCE_ROOT / "pa100k")


def _dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _safe_image_name(value: object) -> str:
    name = _text(value)
    path = Path(name)
    if not name or path.is_absolute() or path.name != name or ".." in path.parts:
        raise RuntimeError(f"unsafe image name: {name!r}")
    return name


def _simuletic_rows(root: Path, groups: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    group_counts: dict[str, int] = {}
    items = [_dict(json.loads(raw)) for raw in (root / "metadata.jsonl").read_text(encoding="utf-8").splitlines()]
    image_counts: dict[str, int] = {}
    for item in items:
        image_name = _safe_image_name(item.get("image"))
        image_counts[image_name] = image_counts.get(image_name, 0) + 1
    for item in items:
        image_name = _safe_image_name(item.get("image"))
        group = image_name.split("_img", maxsplit=1)[0]
        if image_counts.get(image_name) != 1 or not image_name or not (root / image_name).is_file() or group_counts.get(group, 0) >= 5:
            continue
        if len(group_counts) >= groups and group not in group_counts:
            continue
        rows.append(item)
        group_counts[group] = group_counts.get(group, 0) + 1
        if len(group_counts) == groups and all(value >= 5 for value in group_counts.values()):
            break
    return rows


def _pa_rows(root: Path, limit: int) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for raw in (root / "manifest.jsonl").read_text(encoding="utf-8").splitlines()[:limit]:
        item = _dict(json.loads(raw))
        image_name = _safe_image_name(item.get("image_name"))
        if image_name and (root / image_name).is_file():
            rows.append(item)
    return rows


def _person_box(model: torch.nn.Module, image: Image.Image, device: torch.device) -> tuple[list[float], float]:
    tensor = torch.from_numpy(np.array(image)).permute(2, 0, 1).float() / 255
    with torch.inference_mode():
        output = model([tensor.to(device)])[0]
    boxes = output["boxes"].detach().cpu()
    labels = output["labels"].detach().cpu()
    scores = output["scores"].detach().cpu()
    candidates = [index for index, label in enumerate(labels.tolist()) if label == 1]
    if not candidates:
        raise RuntimeError("no person detection")
    index = max(candidates, key=lambda value: float(scores[value]))
    return boxes[index].tolist(), float(scores[index])


def _crop(image: Image.Image, box: list[float], margin: float) -> tuple[Image.Image, list[int]]:
    width, height = image.size
    x1, y1, x2, y2 = box
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    left = max(0, round(x1 - box_width * margin))
    top = max(0, round(y1 - box_height * margin))
    right = min(width, round(x2 + box_width * margin))
    bottom = min(height, round(y2 + box_height * margin))
    return image.crop((left, top, right, bottom)), [left, top, right, bottom]


def _safe_output_root(value: Path) -> Path:
    candidate = (PROJECT_ROOT / value).resolve() if not value.is_absolute() else value.resolve()
    try:
        candidate.relative_to(SOURCE_ROOT)
    except ValueError as error:
        raise SystemExit(f"--output must be under {SOURCE_ROOT}") from error
    if candidate == SOURCE_ROOT or any(
        dataset == candidate or dataset in candidate.parents or candidate in dataset.parents
        for dataset in SOURCE_DATASETS
    ):
        raise SystemExit("--output cannot overlap source dataset directories")
    return candidate


def _remove_stale_outputs(output_root: Path, expected: dict[str, set[str]]) -> list[str]:
    removed: list[str] = []
    for dataset, names in expected.items():
        dataset_root = output_root / dataset
        if not dataset_root.is_dir():
            continue
        for path in dataset_root.iterdir():
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg"} and path.name not in names:
                path.unlink()
                removed.append(str(path.relative_to(PROJECT_ROOT)))
    return removed


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("experiments/data/cctv_proxy/person_only"))
    parser.add_argument("--simuletic-groups", type=int, default=3)
    parser.add_argument("--pa-limit", type=int, default=30)
    parser.add_argument("--margin", type=float, default=0.05)
    parser.add_argument("--threshold", type=float, default=0.20)
    args = parser.parse_args()
    if not 0 <= args.margin <= 0.25:
        raise SystemExit("--margin must be between 0 and 0.25")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    weights = FasterRCNN_MobileNet_V3_Large_320_FPN_Weights.DEFAULT
    model = fasterrcnn_mobilenet_v3_large_320_fpn(weights=weights).eval().to(device)
    weights_filename = Path(weights.url).name
    weights_path = Path(torch.hub.get_dir()) / "checkpoints" / weights_filename
    output_root = _safe_output_root(args.output)
    output_root.mkdir(parents=True, exist_ok=True)
    for dataset in ("simuletic", "pa100k"):
        (output_root / dataset).mkdir(parents=True, exist_ok=True)
    source_rows = {
        "simuletic": _simuletic_rows(SOURCE_ROOT / "simuletic", args.simuletic_groups),
        "pa100k": _pa_rows(SOURCE_ROOT / "pa100k", args.pa_limit),
    }
    expected_names = {
        "simuletic": {_safe_image_name(item.get("image")) for item in source_rows["simuletic"]},
        "pa100k": {_safe_image_name(item.get("image_name")) for item in source_rows["pa100k"]},
    }
    removed_stale_outputs = _remove_stale_outputs(output_root, expected_names)
    manifest: list[dict[str, object]] = []
    for dataset, rows in source_rows.items():
        source_root = SOURCE_ROOT / dataset
        for item in rows:
            image_name = _text(item.get("image")) if dataset == "simuletic" else _text(item.get("image_name"))
            source_path = source_root / image_name
            image = Image.open(source_path).convert("RGB")
            raw_box, score = _person_box(model, image, device)
            if score < args.threshold:
                raise RuntimeError(f"person detection below threshold for {dataset}/{image_name}: {score:.4f}")
            cropped, crop_box = _crop(image, raw_box, args.margin)
            destination = output_root / dataset / image_name
            cropped.save(destination, format="PNG")
            manifest.append(
                {
                    "dataset": dataset,
                    "image": image_name,
                    "source_image": str(source_path.relative_to(PROJECT_ROOT)),
                    "source_size": list(image.size),
                    "detector": "fasterrcnn_mobilenet_v3_large_320_fpn",
                    "detector_weights": "DEFAULT",
                    "person_score": round(score, 6),
                    "raw_box_xyxy": [round(float(value), 3) for value in raw_box],
                    "margin_fraction": args.margin,
                    "crop_box_xyxy": crop_box,
                    "crop_size": list(cropped.size),
                    "output_image": str(destination.relative_to(PROJECT_ROOT)),
                }
            )
        source_manifest = output_root / dataset / ("metadata.jsonl" if dataset == "simuletic" else "manifest.jsonl")
        source_manifest.write_text(
            "\n".join(json.dumps(item, ensure_ascii=False) for item in rows) + "\n",
            encoding="utf-8",
        )
    (output_root / "crop_manifest.jsonl").write_text(
        "\n".join(json.dumps(item, ensure_ascii=False) for item in manifest) + "\n",
        encoding="utf-8",
    )
    summary = {
        "status": "measured",
        "examples": len(manifest),
        "dataset_counts": {dataset: len(rows) for dataset, rows in source_rows.items()},
        "device": str(device),
        "detector": "fasterrcnn_mobilenet_v3_large_320_fpn",
        "weights": "DEFAULT",
        "detector_weights_url": weights.url,
        "detector_weights_file": weights_filename,
        "detector_weights_sha256": _sha256(weights_path) if weights_path.is_file() else None,
        "threshold_configured": args.threshold,
        "margin_fraction": args.margin,
        "removed_stale_outputs": removed_stale_outputs,
        "score_min": min(item["person_score"] for item in manifest),
        "score_median": sorted(item["person_score"] for item in manifest)[len(manifest) // 2],
        "score_max": max(item["person_score"] for item in manifest),
    }
    (output_root / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

