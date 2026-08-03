from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = (PROJECT_ROOT / "experiments" / "results").resolve()


def profile_video(path: Path) -> dict[str, Any]:
    capture = cv2.VideoCapture(str(path))
    if not capture.isOpened():
        raise RuntimeError(f"cannot open video: {path.name}")

    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = float(capture.get(cv2.CAP_PROP_FPS))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    samples: list[float] = []
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % max(frame_count // 12, 1) == 0:
            grayscale = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            samples.append(float(grayscale.mean()))
        frame_index += 1
    capture.release()

    duration = frame_count / fps if fps > 0 else 0.0
    aspect_ratio = width / height if height > 0 else 0.0
    return {
        "fileName": path.name,
        "frameCount": frame_count,
        "fps": round(fps, 4),
        "width": width,
        "height": height,
        "durationSeconds": round(duration, 4),
        "aspectRatio": round(aspect_ratio, 4),
        "orientation": "landscape" if width >= height else "portrait",
        "sampledFrameCount": len(samples),
        "meanLuma": round(sum(samples) / len(samples), 4) if samples else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="append", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--force", action="store_true")
    arguments = parser.parse_args()
    raw_paths = [Path(video).expanduser() for video in arguments.video]
    symlinked = [path.name for path in raw_paths if path.is_symlink()]
    if symlinked:
        raise ValueError(f"symlink input is not allowed: {symlinked}")
    paths = [path.resolve() for path in raw_paths]
    missing = [path.name for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing video files: {missing}")
    raw_output = Path(arguments.output).expanduser()
    if raw_output.is_symlink():
        raise ValueError("symlink output is not allowed")
    output = raw_output.resolve()
    if not output.is_relative_to(RESULTS_ROOT):
        raise ValueError("output must be under experiments/results")
    if output.exists() and not arguments.force:
        raise FileExistsError(f"output exists; use --force to replace: {output.name}")
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schemaVersion": "1.0",
        "status": "profiled_metadata_only",
        "videos": [profile_video(path) for path in paths],
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
