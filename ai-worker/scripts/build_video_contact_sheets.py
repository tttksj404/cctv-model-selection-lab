from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULTS_ROOT = (PROJECT_ROOT / "experiments/results").resolve()


def _sample_indices(frame_count: int, sample_count: int) -> list[int]:
    if frame_count < 1:
        raise ValueError("video has no readable frames")
    count = min(frame_count, sample_count)
    return np.linspace(0, frame_count - 1, num=count, dtype=int).tolist()


def build_contact_sheet(video: Path, output: Path, sample_count: int) -> None:
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise ValueError(f"cannot open video: {video}")
    try:
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        frames: list[np.ndarray] = []
        for frame_index in _sample_indices(frame_count, sample_count):
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue
            target_width = 384
            scale = target_width / frame.shape[1]
            target_height = max(1, round(frame.shape[0] * scale))
            frame = cv2.resize(
                frame,
                (target_width, target_height),
                interpolation=cv2.INTER_AREA,
            )
            timestamp = frame_index / fps if fps > 0 else 0.0
            cv2.rectangle(frame, (0, 0), (190, 28), (0, 0, 0), thickness=-1)
            cv2.putText(
                frame,
                f"{video.stem} {timestamp:05.1f}s",
                (8, 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.48,
                (255, 255, 255),
                1,
                cv2.LINE_AA,
            )
            frames.append(frame)
    finally:
        capture.release()
    if not frames:
        raise ValueError(f"no frames were decoded: {video}")

    columns = 3
    rows = (len(frames) + columns - 1) // columns
    tile_height = max(frame.shape[0] for frame in frames)
    sheet = np.zeros(
        (rows * tile_height, columns * frames[0].shape[1], 3),
        dtype=np.uint8,
    )
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        y = row * tile_height
        x = column * frame.shape[1]
        sheet[y : y + frame.shape[0], x : x + frame.shape[1]] = frame

    output.parent.mkdir(parents=True, exist_ok=True)
    ok, encoded = cv2.imencode(".png", sheet)
    if not ok:
        raise OSError(f"failed to encode contact sheet: {output}")
    output.write_bytes(encoded.tobytes())


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-count", type=int, default=12)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.sample_count < 2:
        raise SystemExit("--sample-count must be at least 2")
    output_dir = args.output_dir.expanduser().resolve()
    if output_dir != RESULTS_ROOT and RESULTS_ROOT not in output_dir.parents:
        raise SystemExit("--output-dir must be under experiments/results")
    for video in args.video:
        video_path = video.expanduser().resolve()
        if not video_path.is_file():
            raise SystemExit(f"video does not exist: {video_path}")
        build_contact_sheet(
            video_path,
            output_dir / f"{video_path.stem}_contact_sheet.png",
            args.sample_count,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

