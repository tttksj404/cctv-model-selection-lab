# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "opencv-python-headless>=4.10",
#   "ultralytics>=8.3",
# ]
# ///
# How to run:
# uv run --with ultralytics --with opencv-python-headless python
# scripts/build_cctv_multitrack_draft.py --help

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import cv2

from qwen_backend.cctv_multitrack import format_track_id

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _short_path_key(value: str) -> str:
    """Return a stable bounded directory key for a long recording identifier."""
    digest = hashlib.blake2b(value.encode("utf-8"), digest_size=8).hexdigest()
    return f"video-{digest}"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--tracker", default="bytetrack.yaml")
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--vid-stride", type=int, default=3)
    parser.add_argument("--sample-every-seconds", type=float, default=0.75)
    parser.add_argument("--max-crops-per-track", type=int, default=16)
    parser.add_argument("--margin", type=float, default=0.05)
    return parser.parse_args()


def _safe_output_root(raw: Path) -> Path:
    candidate = (PROJECT_ROOT / raw).resolve() if not raw.is_absolute() else raw.resolve()
    data_root = (PROJECT_ROOT / "experiments" / "data" / "cctv_real").resolve()
    candidate.relative_to(data_root)
    if candidate == data_root:
        raise SystemExit("--output-root must be a child of experiments/data/cctv_real")
    return candidate


def _write_image(path: Path, image: Any) -> None:
    ok, encoded = cv2.imencode(path.suffix, image)
    if not ok:
        raise OSError(f"image_encode_failed: {path}")
    path.write_bytes(encoded.tobytes())


def _expanded_box(
    bbox: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
    margin: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = bbox
    box_width = max(x2 - x1, 1.0)
    box_height = max(y2 - y1, 1.0)
    return (
        max(0, round(x1 - box_width * margin)),
        max(0, round(y1 - box_height * margin)),
        min(width, round(x2 + box_width * margin)),
        min(height, round(y2 + box_height * margin)),
    )


def _process_video(
    model: Any,
    video_path: Path,
    args: argparse.Namespace,
    root: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"video_open_failed: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    if fps <= 0.0:
        raise RuntimeError(f"video_fps_missing: {video_path}")

    video_id = video_path.stem
    crop_root = root / "crops" / _short_path_key(video_id)
    crop_root.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    saved_per_track: dict[int, int] = defaultdict(int)
    last_saved_frame: dict[int, int] = {}
    observed_track_frames: dict[int, int] = defaultdict(int)
    minimum_gap = max(1, round(fps * args.sample_every_seconds))
    results = model.track(
        source=str(video_path),
        stream=True,
        classes=[0],
        conf=args.confidence,
        tracker=args.tracker,
        device=args.device,
        vid_stride=args.vid_stride,
        persist=False,
        verbose=False,
    )
    processed_frames = 0
    for result_index, result in enumerate(results):
        processed_frames += 1
        frame_index = result_index * args.vid_stride
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            continue
        coordinates = boxes.xyxy.detach().cpu().tolist()
        confidences = boxes.conf.detach().cpu().tolist()
        tracker_ids = boxes.id.detach().cpu().int().tolist()
        for coordinate, confidence, tracker_id in zip(
            coordinates,
            confidences,
            tracker_ids,
            strict=True,
        ):
            observed_track_frames[tracker_id] += 1
            if saved_per_track[tracker_id] >= args.max_crops_per_track:
                continue
            if frame_index - last_saved_frame.get(tracker_id, -minimum_gap) < minimum_gap:
                continue
            bbox = tuple(float(value) for value in coordinate)
            left, top, right, bottom = _expanded_box(
                bbox,
                width=width,
                height=height,
                margin=args.margin,
            )
            crop = result.orig_img[top:bottom, left:right]
            if crop.size == 0:
                continue
            track_id = format_track_id(video_id, tracker_id)
            track_root = crop_root / f"track-{tracker_id:04d}"
            track_root.mkdir(parents=True, exist_ok=True)
            crop_path = track_root / f"{frame_index:06d}.jpg"
            _write_image(crop_path, crop)
            saved_per_track[tracker_id] += 1
            last_saved_frame[tracker_id] = frame_index
            rows.append(
                {
                    "schemaVersion": "cctv-multitrack-v1",
                    "videoId": video_id,
                    "cameraId": f"local-{video_id}",
                    "conditionGroupId": "portrait_room" if height > width else "landscape_room",
                    "sequenceId": video_id,
                    "trackId": track_id,
                    "identityGroupId": None,
                    "split": "unassigned",
                    "framePath": crop_path.relative_to(PROJECT_ROOT).as_posix(),
                    "timestampMs": round(frame_index / fps * 1000),
                    "bbox": [left, top, right, bottom],
                    "quality": round(float(confidence), 6),
                    "qualityFlags": ["detector_track", "needs_identity_review"],
                    "attributes": {
                        "color": [],
                        "clothing": [],
                        "texture": [],
                        "carriedItem": [],
                        "visibility": "not_annotated",
                    },
                }
            )
    return {
        "videoId": video_id,
        "sourcePath": str(video_path),
        "fps": fps,
        "frameCount": frame_count,
        "width": width,
        "height": height,
        "processedFrames": processed_frames,
        "detectedTrackCount": len(observed_track_frames),
        "exportedTrackCount": len(saved_per_track),
        "exportedCropCount": sum(saved_per_track.values()),
        "observedFramesPerTrack": {
            format_track_id(video_id, tracker_id): count
            for tracker_id, count in sorted(observed_track_frames.items())
        },
    }, rows


def main() -> None:
    args = _parse_args()
    if args.vid_stride <= 0 or args.sample_every_seconds <= 0:
        raise SystemExit("stride and sampling interval must be positive")
    if args.max_crops_per_track <= 0:
        raise SystemExit("max crops per track must be positive")
    if not 0.0 <= args.margin <= 0.25:
        raise SystemExit("margin must be between 0 and 0.25")
    root = _safe_output_root(args.output_root)
    root.mkdir(parents=True, exist_ok=True)
    from ultralytics import YOLO

    model = YOLO(args.weights)
    all_rows: list[dict[str, Any]] = []
    videos: list[dict[str, Any]] = []
    for raw_video in args.video:
        video_summary, rows = _process_video(model, Path(raw_video).resolve(), args, root)
        videos.append(video_summary)
        all_rows.extend(rows)
    manifest_path = root / "manifest.jsonl"
    manifest_path.write_text(
        "".join(f"{json.dumps(row, ensure_ascii=False)}\n" for row in all_rows),
        encoding="utf-8",
    )
    summary = {
        "schemaVersion": "cctv-multitrack-summary-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "weights": args.weights,
        "tracker": args.tracker,
        "device": args.device,
        "videos": videos,
        "rows": len(all_rows),
        "identityReviewRequired": True,
        "trackHeldoutMetricsEligible": False,
    }
    (root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
