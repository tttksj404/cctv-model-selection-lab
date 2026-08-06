import subprocess
from datetime import UTC, datetime
from pathlib import Path

import anyio
import pytest

from qwen_backend import storage_transfer
from qwen_backend.central_client import CentralWorkerError
from qwen_backend.worker_protocol import RecordingAnalysisTarget
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_transfer import RecordingEvidenceTransfer, _segment_target


def test_signed_recording_window_is_materialized_atomically(
    monkeypatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, ...]] = []

    def fake_ffmpeg(
        command: tuple[str, ...], timeout_seconds: float
    ) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        assert timeout_seconds == 42
        Path(command[-1]).write_bytes(b"window")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(storage_transfer, "_run_ffmpeg", fake_ffmpeg)
    destination = tmp_path / "cache" / "recording.window.mp4"

    async def scenario() -> Path:
        return await storage_transfer.download_time_window_to_path(
            "https://storage.example/recording.mp4",
            destination,
            start_ms=12_500,
            end_ms=17_750,
            max_bytes=1_024,
            ffmpeg_path="ffmpeg",
            timeout_seconds=42,
        )

    result = anyio.run(scenario)

    assert result == destination
    assert destination.read_bytes() == b"window"
    assert not destination.with_name(".recording.window.part.mp4").exists()
    assert calls[0][0] == "ffmpeg"
    assert calls[0][calls[0].index("-ss") + 1] == "12.500"
    assert calls[0][calls[0].index("-t") + 1] == "5.250"
    assert "https://storage.example/recording.mp4" in calls[0]


def test_segment_target_restores_original_recording_timeline() -> None:
    target = RecordingAnalysisTarget(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        cameraId=41,
        cameraCode="CAM-001",
        cameraName="Gate A",
        recordingObjectKey="recordings/video.mp4",
        recordingDownloadUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        searchFromMs=12_500,
        searchToMs=17_750,
        attempt=1,
    )

    segment = _segment_target(target)

    assert segment.recording_start == datetime(2026, 7, 30, 0, 0, 12, 500_000, tzinfo=UTC)
    assert segment.recording_end == datetime(2026, 7, 30, 0, 0, 17, 750_000, tzinfo=UTC)
    assert segment.search_from_ms == 0
    assert segment.search_to_ms == 5_250


def test_recording_transfer_uses_segment_mode_and_translates_target(tmp_path: Path) -> None:
    class SegmentClient:
        def __init__(self) -> None:
            self.calls: list[dict[str, object]] = []

        async def download_segment(
            self,
            url: str,
            destination: Path,
            *,
            start_ms: int,
            end_ms: int,
            max_bytes: int,
            ffmpeg_path: str,
            timeout_seconds: float,
        ) -> Path:
            self.calls.append(
                {
                    "url": url,
                    "start_ms": start_ms,
                    "end_ms": end_ms,
                    "max_bytes": max_bytes,
                    "ffmpeg_path": ffmpeg_path,
                    "timeout_seconds": timeout_seconds,
                }
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(b"window")
            return destination

    target = RecordingAnalysisTarget(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        cameraId=41,
        cameraCode="CAM-001",
        cameraName="Gate A",
        recordingObjectKey="recordings/video.mp4",
        recordingDownloadUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        searchFromMs=12_500,
        searchToMs=17_750,
        attempt=1,
    )
    client = SegmentClient()
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="test-key",
        worker_id="notebook-test",
        cache_dir=tmp_path / "cache",
        segment_timeout_seconds=42,
    )

    async def scenario() -> tuple[RecordingAnalysisTarget, Path]:
        return await RecordingEvidenceTransfer(settings).download_target_recording(
            client,
            target,
            "lease-1",
        )

    segment, path = anyio.run(scenario)

    assert path.read_bytes() == b"window"
    assert segment.search_from_ms == 0
    assert segment.search_to_ms == 5_250
    assert client.calls == [
        {
            "url": "https://storage.example/video.mp4",
            "start_ms": 12_500,
            "end_ms": 17_750,
            "max_bytes": 5 * 1024 * 1024 * 1024,
            "ffmpeg_path": "ffmpeg",
            "timeout_seconds": 42.0,
        }
    ]


def test_controller_target_without_signed_url_never_uses_direct_object_storage(
    tmp_path: Path,
) -> None:
    class NoDirectStorageClient:
        async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path:
            pytest.fail(f"signed download must not be reached without a URL: {url}")

        async def download_segment(
            self,
            url: str,
            destination: Path,
            *,
            start_ms: int,
            end_ms: int,
            max_bytes: int,
            ffmpeg_path: str,
            timeout_seconds: float,
        ) -> Path:
            pytest.fail(f"signed segment download must not be reached without a URL: {url}")

        async def fetch_target(
            self,
            job_id: int,
            claim_token: str,
        ) -> RecordingAnalysisTarget:
            pytest.fail(f"target refresh must not be reached without a download attempt: {job_id}")

        async def download_object(
            self,
            object_key: str,
            destination: Path,
            *,
            max_bytes: int,
        ) -> Path:
            pytest.fail(f"direct object storage must not be used: {object_key}")

    target = RecordingAnalysisTarget(
        jobId=71,
        caseId=11,
        recordingId=31,
        cameraId=41,
        cameraCode="CAM-001",
        cameraName="Gate A",
        recordingObjectKey="recordings/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        searchFromMs=0,
        searchToMs=5_000,
        attempt=1,
    )
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="test-key",
        worker_id="notebook-test",
        cache_dir=tmp_path / "cache",
    )

    async def scenario() -> None:
        await RecordingEvidenceTransfer(settings).download_target_recording(
            NoDirectStorageClient(),
            target,
            "lease-1",
        )

    with pytest.raises(CentralWorkerError, match="recordingDownloadUrl") as error:
        anyio.run(scenario)

    assert error.value.code == "WORKER_TARGET_MISSING_DOWNLOAD_URL"
