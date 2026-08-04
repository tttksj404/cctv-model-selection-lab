# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10,<3"]
# ///
from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from qwen_backend.cctv_review_queue import ReviewQueueError, build_review_queue
from qwen_backend.cctv_training_contract import (
    CCTVTrainingSample,
    TrainingManifestError,
    load_training_manifest,
)


class ReviewQueueSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cctv-review-queue-summary-v1"]
    status: Literal["needs_human_review"]
    source_rows: int
    queue_rows: int
    augmentation_rows: int
    original_rows: int
    identity_labels_available: Literal[False]
    training_eligible: Literal[False]


def run(input_manifest: Path, workspace: Path, output: Path) -> ReviewQueueSummary:
    workspace = workspace.expanduser().resolve()
    input_path = _inside_workspace(input_manifest, workspace)
    output_path = _inside_workspace(output, workspace)
    if input_path == output_path:
        raise ReviewQueueError("input and output paths must differ")
    try:
        samples = load_training_manifest(input_path)
    except TrainingManifestError as error:
        raise ReviewQueueError(str(error)) from error
    _validate_sample_assets(samples, workspace)
    queue = build_review_queue(samples)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    summary = ReviewQueueSummary(
        schema_version="cctv-review-queue-summary-v1",
        status="needs_human_review",
        source_rows=len(samples),
        queue_rows=len(queue),
        augmentation_rows=sum(
            1 for sample in samples if sample.augmentation != "original"
        ),
        original_rows=sum(1 for sample in samples if sample.augmentation == "original"),
        identity_labels_available=False,
        training_eligible=False,
    )
    summary_path = output_path.with_suffix(".summary.json")
    queue_text = "".join(item.model_dump_json(by_alias=True) + "\n" for item in queue)
    temporary_path = _write_temporary_text(output_path.parent, output_path.name, queue_text)
    temporary_summary_path = _write_temporary_text(
        summary_path.parent, summary_path.name, summary.model_dump_json(indent=2) + "\n"
    )
    try:
        os.replace(temporary_summary_path, summary_path)
        os.replace(temporary_path, output_path)
    finally:
        temporary_path.unlink(missing_ok=True)
        temporary_summary_path.unlink(missing_ok=True)
    return summary


def _inside_workspace(path: Path, workspace: Path) -> Path:
    resolved = (path if path.is_absolute() else workspace / path).resolve()
    try:
        resolved.relative_to(workspace)
    except ValueError as error:
        raise ReviewQueueError(f"path is outside workspace: {path}") from error
    return resolved


def _validate_sample_assets(
    samples: tuple[CCTVTrainingSample, ...], workspace: Path
) -> None:
    for sample in samples:
        for field_name, path_value, expected_hash in (
            ("sourceFramePath", sample.source_frame_path, sample.source_frame_sha256),
            ("cropPath", sample.crop_path, sample.crop_sha256),
        ):
            path = Path(path_value)
            if path.is_absolute() or ".." in path.parts:
                raise ReviewQueueError(f"{field_name} is outside workspace: {path_value}")
            resolved = (workspace / path).resolve()
            try:
                resolved.relative_to(workspace)
            except ValueError as error:
                raise ReviewQueueError(
                    f"{field_name} is outside workspace: {path_value}"
                ) from error
            if not resolved.is_file():
                raise ReviewQueueError(f"{field_name} does not exist: {path_value}")
            if expected_hash is not None:
                actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
                if actual_hash != expected_hash.lower():
                    raise ReviewQueueError(f"{field_name} hash does not match: {path_value}")


def _write_temporary_text(directory: Path, target_name: str, content: str) -> Path:
    temporary = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix=f".{target_name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary_path = Path(temporary.name)
    try:
        temporary.write(content)
    except OSError:
        temporary.close()
        temporary_path.unlink(missing_ok=True)
        raise
    temporary.close()
    return temporary_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        summary = run(args.input_manifest, args.workspace, args.output)
    except ReviewQueueError as error:
        print(json.dumps({"status": "blocked", "error": str(error)}, ensure_ascii=False))
        return 1
    print(summary.model_dump_json())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
