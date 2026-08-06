from __future__ import annotations

import contextlib
import json
import re
import shutil
import subprocess
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

import anyio
import pytest

from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.worker_protocol import RecordingAnalysisTarget
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_transfer import RecordingEvidenceTransfer


@dataclass(frozen=True)
class _RequestTrace:
    path: str
    headers: dict[str, str]


@dataclass
class _PresignedRecordingServer:
    video_path: Path
    target_payload: dict[str, object] | None = None
    requests: list[_RequestTrace] = field(default_factory=list)

    def __post_init__(self) -> None:
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                owner._handle(self, write_body=True)

            def do_HEAD(self) -> None:
                owner._handle(self, write_body=False)

            def log_message(self, format: str, *args: object) -> None:
                del format, args

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self._thread.start()

    def close(self) -> None:
        self._server.shutdown()
        self._thread.join(timeout=5)
        self._server.server_close()

    def _handle(self, request: BaseHTTPRequestHandler, *, write_body: bool) -> None:
        path = urlsplit(request.path).path
        headers = {name.lower(): value for name, value in request.headers.items()}
        self.requests.append(_RequestTrace(path=path, headers=headers))

        if path.endswith("/target"):
            if self.target_payload is None:
                request.send_error(500)
                return
            body = json.dumps({"data": self.target_payload}).encode("utf-8")
            request.send_response(200)
            request.send_header("Content-Type", "application/json")
            request.send_header("Content-Length", str(len(body)))
            request.end_headers()
            if write_body:
                request.wfile.write(body)
            return
        if path == "/expired.mp4":
            request.send_response(403)
            request.send_header("Content-Length", "0")
            request.end_headers()
            return
        if path == "/mini.mp4":
            self._write_video(request, write_body=write_body)
            return
        request.send_error(404)

    def _write_video(self, request: BaseHTTPRequestHandler, *, write_body: bool) -> None:
        video = self.video_path.read_bytes()
        start = 0
        end = len(video) - 1
        status = 200
        requested_range = request.headers.get("Range")
        if requested_range is not None:
            matched = re.fullmatch(r"bytes=(\d+)-(\d*)", requested_range)
            if matched is not None:
                start = min(int(matched.group(1)), end)
                if matched.group(2):
                    end = min(int(matched.group(2)), end)
                if start <= end:
                    status = 206
        body = video[start : end + 1]
        request.send_response(status)
        request.send_header("Content-Type", "video/mp4")
        request.send_header("Accept-Ranges", "bytes")
        request.send_header("Content-Length", str(len(body)))
        if status == 206:
            request.send_header("Content-Range", f"bytes {start}-{end}/{len(video)}")
        request.end_headers()
        if write_body:
            request.wfile.write(body)


@contextlib.contextmanager
def _serve_presigned_recording(video_path: Path) -> Iterator[_PresignedRecordingServer]:
    server = _PresignedRecordingServer(video_path)
    server.start()
    try:
        yield server
    finally:
        server.close()


def _make_mini_mp4(path: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        pytest.skip("ffmpeg is required for the signed recording integration test")
    completed = subprocess.run(
        (
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=160x120:rate=10",
            "-t",
            "2",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-movflags",
            "+faststart",
            str(path),
        ),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr[-1_000:]
    assert path.is_file() and path.stat().st_size > 0


def _target_payload(base_url: str, *, download_path: str, size_bytes: int) -> dict[str, object]:
    return {
        "jobId": 71,
        "caseId": 11,
        "recordingId": 31,
        "cameraId": 41,
        "cameraCode": "CAM-001",
        "cameraName": "Gate A",
        "recordingObjectKey": "recordings/CAM-001/mini.mp4",
        "recordingDownloadUrl": f"{base_url}{download_path}?signature=integration-test",
        "recordingDownloadUrlExpiresInSeconds": 900,
        "recordingFileSizeBytes": size_bytes,
        "recordingContentType": "video/mp4",
        "recordingStart": "2026-08-06T00:00:00Z",
        "recordingEnd": "2026-08-06T00:00:02Z",
        "prompt": "gray shirt, black pants",
        "exclusionPrompt": None,
        "searchStart": "2026-08-06T00:00:00Z",
        "searchEnd": "2026-08-06T00:00:02Z",
        "analysisStart": "2026-08-06T00:00:00Z",
        "analysisEnd": "2026-08-06T00:00:02Z",
        "searchArea": "test gate",
        "attempt": 1,
    }


def test_segmented_presigned_recording_refreshes_once_without_worker_headers(
    tmp_path: Path,
) -> None:
    mini_video = tmp_path / "mini.mp4"
    _make_mini_mp4(mini_video)

    with _serve_presigned_recording(mini_video) as server:
        initial_target = RecordingAnalysisTarget.model_validate(
            _target_payload(
                server.base_url,
                download_path="/expired.mp4",
                size_bytes=mini_video.stat().st_size,
            )
        )
        server.target_payload = _target_payload(
            server.base_url,
            download_path="/mini.mp4",
            size_bytes=mini_video.stat().st_size,
        )
        settings = NotebookWorkerSettings(
            central_api_url=server.base_url,
            api_key="worker-key-for-integration-test",
            auth_mode="worker",
            worker_id="mini-recording-test",
            cache_dir=tmp_path / "cache",
            output_dir=tmp_path / "output",
            download_window_mode="segment",
        )

        async def scenario() -> tuple[RecordingAnalysisTarget, Path]:
            async with CentralWorkerClient(
                base_url=settings.central_api_url,
                api_key=settings.api_key.get_secret_value(),
                auth_mode=settings.auth_mode,
                worker_id=settings.worker_id,
            ) as client:
                return await RecordingEvidenceTransfer(settings).download_target_recording(
                    client,
                    initial_target,
                    "claim-token-for-integration-test",
                )

        target, segment_path = anyio.run(scenario)

    assert target.recording_download_url is not None
    assert target.recording_download_url.endswith("/mini.mp4?signature=integration-test")
    assert target.recording_download_url_expires_in_seconds == 900
    assert target.recording_file_size_bytes == mini_video.stat().st_size
    assert target.recording_content_type == "video/mp4"
    assert segment_path.is_file() and segment_path.stat().st_size > 0

    target_requests = [request for request in server.requests if request.path.endswith("/target")]
    storage_requests = [
        request for request in server.requests if request.path in {"/expired.mp4", "/mini.mp4"}
    ]
    assert len(target_requests) == 1
    assert target_requests[0].headers["x-worker-key"] == "worker-key-for-integration-test"
    assert target_requests[0].headers["x-worker-claim-token"] == "claim-token-for-integration-test"
    assert any(request.path == "/expired.mp4" for request in storage_requests)
    assert any(request.path == "/mini.mp4" for request in storage_requests)
    assert all("x-worker-key" not in request.headers for request in storage_requests)
    assert all("x-worker-claim-token" not in request.headers for request in storage_requests)
