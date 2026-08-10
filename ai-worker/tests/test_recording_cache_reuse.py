from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import anyio

from qwen_backend.candidate_runtime import CandidateRuntimeResponse
from qwen_backend.central_client import CentralWorkerError
from qwen_backend.recording_cache import RecordingCacheManifest
from qwen_backend.recording_job_executor import RecordingJobExecutor
from qwen_backend.worker_protocol import RecordingAnalysisTarget
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_transfer import RecordingEvidenceTransfer


class CountingRecordingClient:
    def __init__(self) -> None:
        self.full_downloads = 0
        self.segment_downloads = 0

    async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path:
        self.full_downloads += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"video")
        return destination

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
        self.segment_downloads += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"window")
        return destination

    async def fetch_target(
        self,
        job_id: int,
        claim_token: str | None,
    ) -> RecordingAnalysisTarget:
        raise CentralWorkerError("target refresh was not expected")


class CountingObjectClient:
    def __init__(self) -> None:
        self.downloads = 0

    async def download_object(self, object_key: str, destination: Path, *, max_bytes: int) -> Path:
        self.downloads += 1
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"full-video")
        return destination


def _target(job_id: int, *, start_ms: int = 0, end_ms: int = 5_000) -> RecordingAnalysisTarget:
    return RecordingAnalysisTarget.model_validate(
        {
            "jobId": job_id,
            "caseId": 11,
            "recordingId": 31,
            "cameraId": 41,
            "cameraCode": "CAM-001",
            "cameraName": "Gate A",
            "recordingObjectKey": "recordings/CAM-001/video.mp4",
            "recordingDownloadUrl": "https://storage.example/video.mp4",
            "recordingFileSizeBytes": 5,
            "recordingStart": datetime(2026, 7, 30, tzinfo=UTC),
            "recordingEnd": datetime(2026, 7, 30, 1, tzinfo=UTC),
            "prompt": "red jacket",
            "searchFromMs": start_ms,
            "searchToMs": end_ms,
            "attempt": 1,
        }
    )


def test_segment_recording_is_reused_for_a_new_job_with_the_same_source_key(
    tmp_path: Path,
) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    transfer = RecordingEvidenceTransfer(settings)

    async def scenario() -> tuple[Path, Path]:
        _, first_path = await transfer.download_target_recording(
            client,
            _target(71),
            "lease-1",
        )
        _, second_path = await transfer.download_target_recording(
            client,
            _target(72),
            "lease-2",
        )
        return first_path, second_path

    first_path, second_path = anyio.run(scenario)

    assert first_path == second_path
    assert first_path.read_bytes() == b"window"
    assert first_path.with_suffix(".manifest.json").is_file()
    assert client.segment_downloads == 1
    assert client.full_downloads == 0


def test_same_object_key_reuses_segment_when_requested_window_differs(
    tmp_path: Path,
) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    transfer = RecordingEvidenceTransfer(settings)

    async def scenario() -> tuple[RecordingAnalysisTarget, Path]:
        await transfer.download_target_recording(
            client,
            _target(71, start_ms=3_486, end_ms=32_105),
            "lease-1",
        )
        return await transfer.download_target_recording(
            client,
            _target(72, start_ms=3_479, end_ms=32_105),
            "lease-2",
        )

    reused_target, path = anyio.run(scenario)

    assert path.name == "video__3486-32105.window.mp4"
    assert reused_target.recording_start == _target(72).recording_start + timedelta(
        milliseconds=3_486
    )
    assert reused_target.search_from_ms == 0
    assert reused_target.search_to_ms == 28_619
    assert client.segment_downloads == 1


def test_segment_recording_is_reused_from_a_manifest_with_a_noncanonical_filename(
    tmp_path: Path,
) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    target = _target(71)
    recordings_dir = settings.cache_dir / "recordings"
    recordings_dir.mkdir(parents=True)
    cached_path = recordings_dir / "legacy-cache-name.mp4"
    cached_path.write_bytes(b"window")
    manifest_path = cached_path.with_suffix(".manifest.json")
    manifest_path.write_text(
        RecordingCacheManifest(
            recording_object_key=target.recording_object_key,
            recording_file_size_bytes=9_999,
            local_file_size_bytes=cached_path.stat().st_size,
            mode="segment",
            search_from_ms=target.search_from_ms,
            search_to_ms=target.search_to_ms,
            complete=True,
        ).model_dump_json(),
        encoding="utf-8",
    )

    async def scenario() -> Path:
        _, path = await RecordingEvidenceTransfer(settings).download_target_recording(
            client,
            target,
            "lease-1",
        )
        return path

    path = anyio.run(scenario)

    assert path == cached_path
    assert path.read_bytes() == b"window"
    assert client.segment_downloads == 0
    assert client.full_downloads == 0


def test_cache_manifest_with_another_recording_object_key_is_not_reused(
    tmp_path: Path,
) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    target = _target(71)
    recordings_dir = settings.cache_dir / "recordings"
    recordings_dir.mkdir(parents=True)
    cached_path = recordings_dir / "wrong-source.mp4"
    cached_path.write_bytes(b"wrong")
    cached_path.with_suffix(".manifest.json").write_text(
        RecordingCacheManifest(
            recording_object_key="recordings/CAM-001/another-video.mp4",
            recording_file_size_bytes=None,
            local_file_size_bytes=cached_path.stat().st_size,
            mode="segment",
            search_from_ms=target.search_from_ms,
            search_to_ms=target.search_to_ms,
            complete=True,
        ).model_dump_json(),
        encoding="utf-8",
    )

    async def scenario() -> Path:
        _, path = await RecordingEvidenceTransfer(settings).download_target_recording(
            client,
            target,
            "lease-1",
        )
        return path

    path = anyio.run(scenario)

    assert path != cached_path
    assert path.read_bytes() == b"window"
    assert client.segment_downloads == 1


def test_legacy_job_file_without_manifest_is_not_reused(tmp_path: Path) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    legacy_path = settings.cache_dir / "job-49-attempt-1.window.mp4"
    legacy_path.parent.mkdir(parents=True)
    legacy_path.write_bytes(b"unknown-source")

    async def scenario() -> Path:
        _, path = await RecordingEvidenceTransfer(settings).download_target_recording(
            client,
            _target(71),
            "lease-1",
        )
        return path

    path = anyio.run(scenario)

    assert path != legacy_path
    assert client.segment_downloads == 1


def test_changed_segment_file_is_downloaded_again(tmp_path: Path) -> None:
    client = CountingRecordingClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "segment",
        }
    )
    transfer = RecordingEvidenceTransfer(settings)

    async def scenario() -> Path:
        _, path = await transfer.download_target_recording(client, _target(71), "lease-1")
        path.write_bytes(b"corrupt")
        _, reused_path = await transfer.download_target_recording(client, _target(72), "lease-2")
        return reused_path

    path = anyio.run(scenario)

    assert path.read_bytes() == b"window"
    assert client.segment_downloads == 2


def test_full_recording_cache_can_serve_a_segment_request(tmp_path: Path) -> None:
    client = CountingRecordingClient()
    full_settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
            "download_window_mode": "analyze",
        }
    )
    segment_settings = full_settings.model_copy(update={"download_window_mode": "segment"})

    async def scenario() -> tuple[RecordingAnalysisTarget, Path]:
        await RecordingEvidenceTransfer(full_settings).download_target_recording(
            client,
            _target(71),
            "lease-1",
        )
        reused_target, path = await RecordingEvidenceTransfer(
            segment_settings
        ).download_target_recording(
            client,
            _target(72, start_ms=10_000, end_ms=15_000),
            "lease-2",
        )
        return reused_target, path

    reused_target, path = anyio.run(scenario)

    assert path.read_bytes() == b"video"
    assert reused_target.search_from_ms == 10_000
    assert reused_target.search_to_ms == 15_000
    assert client.full_downloads == 1
    assert client.segment_downloads == 0


def test_device_api_path_uses_object_key_filename_and_reuses_full_recording(
    tmp_path: Path,
) -> None:
    client = CountingObjectClient()
    settings = NotebookWorkerSettings.model_validate(
        {
            "central_api_url": "https://central.example",
            "api_key": "test-key",
            "worker_id": "notebook-test",
            "cache_dir": tmp_path / "cache",
        }
    )
    executor = RecordingJobExecutor(
        settings,
        lambda _request: CandidateRuntimeResponse(
            model_key=settings.model_key,
            candidates=(),
        ),
    )

    async def scenario() -> tuple[Path, Path]:
        first = await executor._download_recording_with_cache(  # pyright: ignore[reportPrivateUsage]
            client,  # type: ignore[arg-type]
            "recordings/CAM-001/segment-123.mp4",
        )
        second = await executor._download_recording_with_cache(  # pyright: ignore[reportPrivateUsage]
            client,  # type: ignore[arg-type]
            "recordings/CAM-001/segment-123.mp4",
        )
        return first, second

    first, second = anyio.run(scenario)

    assert first == second
    assert first.name == "segment-123.mp4"
    assert first.read_bytes() == b"full-video"
    assert first.with_suffix(".manifest.json").is_file()
    assert client.downloads == 1

