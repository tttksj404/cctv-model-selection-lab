from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from qwen_backend.recording_cache import RecordingCache
from qwen_backend.worker_protocol import RecordingAnalysisTarget


def _target(
    recording_object_key: str,
    *,
    start_ms: int = 0,
    end_ms: int = 30_000,
) -> RecordingAnalysisTarget:
    return RecordingAnalysisTarget.model_validate(
        {
            "jobId": 71,
            "caseId": 11,
            "recordingId": 31,
            "cameraId": 41,
            "cameraCode": "CAM-001",
            "cameraName": "Gate A",
            "recordingObjectKey": recording_object_key,
            "recordingDownloadUrl": "https://storage.example/recording.mp4",
            "recordingStart": datetime(2026, 8, 7, tzinfo=UTC),
            "recordingEnd": datetime(2026, 8, 7, 1, tzinfo=UTC),
            "prompt": "gray shirt, black pants",
            "searchFromMs": start_ms,
            "searchToMs": end_ms,
            "attempt": 1,
        }
    )


def test_full_cache_uses_recording_object_key_filename(tmp_path: Path) -> None:
    paths = RecordingCache(tmp_path / "cache").paths(
        _target("recordings/CAM-001/20260807T120000_123e4567-e89b-12d3-a456-426614174000.mp4"),
        "full",
    )

    assert paths.video_path == (
        tmp_path
        / "cache"
        / "recordings"
        / "20260807T120000_123e4567-e89b-12d3-a456-426614174000.mp4"
    )
    assert paths.manifest_path.name == (
        "20260807T120000_123e4567-e89b-12d3-a456-426614174000.manifest.json"
    )


def test_segment_cache_keeps_filename_and_separates_windows(tmp_path: Path) -> None:
    cache = RecordingCache(tmp_path / "cache")
    target = _target("recordings/CAM-001/segment-123.mp4")

    first = cache.paths(target, "segment")
    second = cache.paths(
        target.model_copy(update={"search_from_ms": 30_000, "search_to_ms": 60_000}),
        "segment",
    )

    assert first.video_path.name == "segment-123__0-30000.window.mp4"
    assert second.video_path.name == "segment-123__30000-60000.window.mp4"
    assert first.video_path != second.video_path


def test_unsafe_object_key_basename_falls_back_to_hashed_filename(tmp_path: Path) -> None:
    paths = RecordingCache(tmp_path / "cache").paths(
        _target("recordings/CAM-001/../bad:name.mp4"),
        "full",
    )

    assert paths.video_path.name.startswith("recording-")
    assert paths.video_path.suffix == ".mp4"


def test_worker_source_does_not_build_job_id_video_cache_paths() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "qwen_backend"
    video_cache_path = re.compile(r"cache_dir\s*/\s*f[\"']job-[^\"']+\.mp4")

    for source_path in (
        source_root / "recording_job_executor.py",
        source_root / "worker_transfer.py",
    ):
        source = source_path.read_text(encoding="utf-8")
        assert video_cache_path.search(source) is None, source_path

