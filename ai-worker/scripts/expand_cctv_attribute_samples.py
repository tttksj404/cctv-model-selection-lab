from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path
from typing import Protocol

from PIL import Image, ImageEnhance, ImageFilter
from PIL.Image import Resampling

from qwen_backend.cctv_sample_expansion import (
    AugmentationName,
    ExpandedSample,
    ExpansionSummary,
    SampleExpansionError,
    augmentation_names,
    crop_box_for_frame,
    make_sample,
    read_draft_manifest,
)


class _ResizableImage(Protocol):
    def resize(self, size: tuple[int, int], resample: Resampling) -> Image.Image: ...


def _resize(image: _ResizableImage, size: tuple[int, int]) -> Image.Image:
    return image.resize(size, Resampling.BILINEAR)


def _apply_augmentation(image: Image.Image, name: AugmentationName) -> Image.Image:
    match name:
        case "original":
            return image.copy()
        case "brightness_low":
            return ImageEnhance.Brightness(image).enhance(0.75)
        case "brightness_high":
            return ImageEnhance.Brightness(image).enhance(1.25)
        case "contrast_low":
            return ImageEnhance.Contrast(image).enhance(0.75)
        case "contrast_high":
            return ImageEnhance.Contrast(image).enhance(1.25)
        case "blur":
            return image.filter(ImageFilter.GaussianBlur(radius=1.2))
        case "low_resolution":
            small_size = (max(1, image.width // 2), max(1, image.height // 2))
            small = _resize(image, small_size)
            return _resize(small, image.size)


def _safe_path(path: Path, workspace: Path) -> Path:
    resolved = path.resolve()
    try:
        resolved.relative_to(workspace.resolve())
    except ValueError as error:
        raise SampleExpansionError(f"path is outside workspace: {path}") from error
    return resolved


def _safe_segment(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).strip()
    if (
        not normalized
        or normalized in {".", ".."}
        or any(char in '<>:"/\\|?*' or ord(char) < 32 for char in normalized)
    ):
        raise SampleExpansionError(f"unsafe output path segment: {value}")
    return normalized


def run(
    input_manifest: Path,
    workspace: Path,
    output_root: Path,
    output_manifest: Path,
    margin: float,
) -> ExpansionSummary:
    rows = read_draft_manifest(_safe_path(input_manifest, workspace))
    workspace = workspace.resolve()
    output_root = _safe_path(output_root, workspace)
    output_manifest = _safe_path(output_manifest, workspace)
    output_root.mkdir(parents=True, exist_ok=True)
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    names = augmentation_names()
    output_rows: list[ExpandedSample] = []
    for index, row in enumerate(rows):
        source_frame_path = _safe_path(workspace / row.frame_path, workspace)
        if not source_frame_path.is_file():
            raise SampleExpansionError(f"source frame is missing: {source_frame_path}")
        with Image.open(source_frame_path) as source:
            image = source.convert("RGB")
            crop_box = crop_box_for_frame(image.size, row.bbox, margin)
            crop = image.crop(crop_box)
            for augmentation in names:
                augmented = _apply_augmentation(crop, augmentation)
                relative_directory = Path(_safe_segment(row.video_id)) / _safe_segment(row.track_id)
                crop_directory = _safe_path(output_root / relative_directory, workspace)
                crop_directory.mkdir(parents=True, exist_ok=True)
                crop_path = _safe_path(
                    crop_directory / f"{index:06d}-{augmentation}.png", workspace
                )
                temporary_crop_path = crop_path.with_suffix(".tmp.png")
                augmented.save(temporary_crop_path, format="PNG", optimize=True)
                temporary_crop_path.replace(crop_path)
                output_rows.append(
                    make_sample(
                        row,
                        source_frame_path,
                        crop_path,
                        augmentation,
                        workspace,
                        index,
                    )
                )
    temporary_manifest = output_manifest.with_suffix(".tmp.jsonl")
    with temporary_manifest.open("w", encoding="utf-8") as handle:
        for output_row in output_rows:
            handle.write(output_row.model_dump_json(by_alias=True) + "\n")
    temporary_manifest.replace(output_manifest)
    return ExpansionSummary(
        schema_version="cctv-attribute-expansion-summary-v1",
        status="unreviewed_teacher_ready",
        source_rows=len(rows),
        expanded_rows=len(output_rows),
        augmentations=names,
        source_videos=tuple(sorted({row.video_id for row in rows})),
        source_split_policy="preserved_in_source_split_unassigned_until_review",
        identity_labels_available=False,
        track_heldout_metrics_eligible=False,
        training_eligible=False,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--margin", type=float, default=0.08)
    args = parser.parse_args()
    try:
        summary = run(
            args.input_manifest,
            args.workspace,
            args.output_root,
            args.output_manifest,
            args.margin,
        )
    except SampleExpansionError as error:
        raise SystemExit(str(error)) from error
    summary_path = args.output_manifest.with_suffix(".summary.json")
    temporary_summary_path = summary_path.with_suffix(".tmp.json")
    temporary_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
    temporary_summary_path.replace(summary_path)
    print(summary.model_dump_json())


if __name__ == "__main__":
    main()
