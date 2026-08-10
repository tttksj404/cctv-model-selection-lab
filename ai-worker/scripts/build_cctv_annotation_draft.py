from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qwen_backend.cctv_annotation import PersonDetection, select_primary_detection


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--frame-root", type=Path, required=True)
    parser.add_argument("--weights", default="yolo11n.pt")
    parser.add_argument("--sample-every-seconds", type=float, default=1.0)
    parser.add_argument("--confidence", type=float, default=0.25)
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--case-id", default="local-cctv-20260723")
    parser.add_argument("--camera-id", default="camera-local-review")
    return parser.parse_args()


def process_video(
    model: Any,
    video_path: Path,
    args: argparse.Namespace,
) -> tuple[list[dict[str, object]], dict[str, object]]:
    import cv2

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"video_open_failed: {video_path}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    if fps <= 0.0:
        capture.release()
        raise RuntimeError(f"video_fps_missing: {video_path}")
    stride = max(1, round(fps * args.sample_every_seconds))
    video_id = video_path.stem
    condition_group = "portrait_fisheye" if height > width else "landscape_room"
    frame_dir = args.frame_root / video_id
    frame_dir.mkdir(parents=True, exist_ok=True)
    track_id = f"{video_id}-draft-track-0001"
    rows: list[dict[str, object]] = []
    sampled = 0
    detected = 0
    frame_index = 0
    while True:
        ok, frame = capture.read()
        if not ok:
            break
        if frame_index % stride == 0:
            sampled += 1
            result = model.predict(
                frame,
                classes=[0],
                conf=args.confidence,
                device=args.device,
                verbose=False,
            )[0]
            detections: list[PersonDetection] = []
            if result.boxes is not None:
                coordinates = result.boxes.xyxy.detach().cpu().tolist()
                confidences = result.boxes.conf.detach().cpu().tolist()
                for coordinate, confidence in zip(coordinates, confidences, strict=True):
                    detections.append(
                        PersonDetection(
                            x1=float(coordinate[0]),
                            y1=float(coordinate[1]),
                            x2=float(coordinate[2]),
                            y2=float(coordinate[3]),
                            confidence=float(confidence),
                        )
                    )
            selected = select_primary_detection(tuple(detections))
            frame_name = f"{frame_index:06d}.jpg"
            frame_path = frame_dir / frame_name
            if not cv2.imwrite(str(frame_path), frame):
                capture.release()
                raise RuntimeError(f"frame_write_failed: {frame_path}")
            if selected is not None:
                detected += 1
            rows.append(
                {
                    "schemaVersion": "cctv-track-v1.1",
                    "caseId": args.case_id,
                    "videoId": video_id,
                    "cameraId": args.camera_id,
                    "conditionGroupId": condition_group,
                    "sequenceId": video_id,
                    "trackId": track_id,
                    "split": "test",
                    "targetRole": "unknown",
                    "identityGroupId": None,
                    "framePath": str(frame_path.as_posix()),
                    "timestampMs": round(frame_index / fps * 1000.0),
                    "bbox": (
                        [selected.x1, selected.y1, selected.x2, selected.y2]
                        if selected is not None
                        else [0.0, 0.0, 0.0, 0.0]
                    ),
                    "maskPath": None,
                    "quality": selected.confidence if selected is not None else 0.0,
                    "qualityFlags": ["detector_candidate", "needs_human_review"],
                    "attributes": {
                        "color": [],
                        "clothing": [],
                        "texture": [],
                        "carriedItem": [],
                        "visibility": "not_annotated",
                    },
                    "attributeEvidenceFrameIds": [],
                }
            )
        frame_index += 1
    capture.release()
    return rows, {
        "videoId": video_id,
        "sourcePath": str(video_path),
        "sourceVideoBytes": video_path.stat().st_size,
        "sourceVideoSha256": sha256_file(video_path),
        "fps": fps,
        "totalFrames": total_frames,
        "width": width,
        "height": height,
        "sampleStride": stride,
        "sampledFrames": sampled,
        "framesWithPrimaryPerson": detected,
        "draftTrackId": track_id,
        "identityGroupIdAssigned": False,
    }


def main() -> None:
    args = parse_args()
    if args.sample_every_seconds <= 0.0:
        raise ValueError("sample-every-seconds must be positive")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.frame_root.mkdir(parents=True, exist_ok=True)
    try:
        from ultralytics import YOLO
    except ModuleNotFoundError as exc:
        raise SystemExit(
            "missing runtime dependency: install ultralytics and opencv-python-headless"
        ) from exc
    model = YOLO(args.weights)
    all_rows: list[dict[str, object]] = []
    videos: list[dict[str, object]] = []
    for raw_path in args.video:
        rows, video_summary = process_video(model, Path(raw_path).resolve(), args)
        all_rows.extend(rows)
        videos.append(video_summary)
    with args.output.open("w", encoding="utf-8") as handle:
        for row in all_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    summary = {
        "schemaVersion": "cctv-track-draft-summary-v1",
        "generatedAt": datetime.now(UTC).isoformat(),
        "weights": args.weights,
        "sampleEverySeconds": args.sample_every_seconds,
        "confidence": args.confidence,
        "videos": videos,
        "rows": len(all_rows),
        "evaluationEligibility": {
            "identityLabelsAvailable": False,
            "trackHeldoutMetricsEligible": False,
            "proxyMetricsReusedAsIdentity": False,
        },
        "annotationStatus": "draft_needs_human_review",
    }
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

