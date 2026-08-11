from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TrackFrame:
    track_id: int
    frame_index: int
    frame_offset_ms: int
    crop_path: Path
    left: int
    top: int
    right: int
    bottom: int
    detector_confidence: float


def _expanded_box(
    coordinates: tuple[float, float, float, float],
    *,
    width: int,
    height: int,
    margin: float,
) -> tuple[int, int, int, int]:
    x1, y1, x2, y2 = coordinates
    box_width = max(x2 - x1, 1.0)
    box_height = max(y2 - y1, 1.0)
    return (
        max(0, round(x1 - box_width * margin)),
        max(0, round(y1 - box_height * margin)),
        min(width, round(x2 + box_width * margin)),
        min(height, round(y2 + box_height * margin)),
    )


def detect_person_tracks(
    video_path: Path,
    output_dir: Path,
    *,
    weights: str,
    tracker: str,
    device: str,
    confidence: float,
    stride: int,
    sample_every_seconds: float,
    max_crops_per_track: int,
    margin: float,
) -> tuple[TrackFrame, ...]:
    import cv2
    from ultralytics import YOLO

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise RuntimeError(f"video_open_failed: {video_path.name}")
    fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
    capture.release()
    if fps <= 0.0 or width <= 0 or height <= 0:
        raise RuntimeError("video_metadata_invalid")

    model = YOLO(weights)
    results = model.track(
        source=str(video_path),
        stream=True,
        classes=[0],
        conf=confidence,
        tracker=tracker,
        device=device,
        vid_stride=stride,
        persist=True,
        verbose=False,
    )
    frames: list[TrackFrame] = []
    saved_per_track: dict[int, int] = defaultdict(int)
    last_saved_frame: dict[int, int] = {}
    minimum_gap = max(1, round(fps * sample_every_seconds))
    track_root = output_dir / "tracks"
    track_root.mkdir(parents=True, exist_ok=True)

    for result_index, result in enumerate(results):
        frame_index = result_index * stride
        boxes = result.boxes
        if boxes is None or boxes.id is None:
            continue
        coordinates = boxes.xyxy.detach().cpu().tolist()
        confidences = boxes.conf.detach().cpu().tolist()
        tracker_ids = boxes.id.detach().cpu().int().tolist()
        for coordinate, detection_confidence, tracker_id in zip(
            coordinates,
            confidences,
            tracker_ids,
            strict=True,
        ):
            tracker_id = int(tracker_id)
            if saved_per_track[tracker_id] >= max_crops_per_track:
                continue
            if frame_index - last_saved_frame.get(tracker_id, -minimum_gap) < minimum_gap:
                continue
            values = tuple(float(value) for value in coordinate)
            left, top, right, bottom = _expanded_box(
                values,
                width=width,
                height=height,
                margin=margin,
            )
            crop = result.orig_img[top:bottom, left:right]
            if crop.size == 0:
                continue
            crop_path = track_root / f"track-{tracker_id}-{frame_index:08d}.jpg"
            if not cv2.imwrite(str(crop_path), crop):
                raise OSError(f"crop_write_failed: {crop_path.name}")
            frames.append(
                TrackFrame(
                    track_id=tracker_id,
                    frame_index=frame_index,
                    frame_offset_ms=round(frame_index / fps * 1_000),
                    crop_path=crop_path,
                    left=left,
                    top=top,
                    right=right,
                    bottom=bottom,
                    detector_confidence=float(detection_confidence),
                )
            )
            saved_per_track[tracker_id] += 1
            last_saved_frame[tracker_id] = frame_index
    return tuple(frames)
