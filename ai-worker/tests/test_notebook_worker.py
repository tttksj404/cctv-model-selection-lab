from __future__ import annotations

import json
import os
import time
from pathlib import Path

import anyio
import httpx2
import pytest

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.notebook_worker import (
    NotebookWorker,
    NotebookWorkerSettings,
    _load_worker_env_file,
)
from qwen_backend.worker_protocol import RecordingAnalysisTarget


class FixtureEngine:
    model_key = "fixture-hybrid-v1"

    def __init__(self) -> None:
        self.similarity_threshold: float | None = -1.0

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        self.similarity_threshold = request.similarity_threshold
        time.sleep(0.7)
        frame_path = request.output_dir / "frame-1250.jpg"
        crop_path = request.output_dir / "track-3.jpg"
        frame_path.write_bytes(b"frame")
        crop_path.write_bytes(b"crop")
        return CandidateRuntimeResponse(
            modelKey=self.model_key,
            candidates=(
                RuntimeCandidate(
                    candidateKey="track-3",
                    frameOffsetMs=1_250,
                    similarity=0.91,
                    framePath=frame_path,
                    cropPath=crop_path,
                    boundingBox=RuntimeBoundingBox(x=10, y=20, width=30, height=40),
                    attributeSummary="fixture",
                ),
            ),
        )


class RefreshingDownloadClient:
    def __init__(self, refreshed_target: RecordingAnalysisTarget) -> None:
        self.refreshed_target = refreshed_target
        self.downloaded_urls: list[str] = []
        self.fetches: list[tuple[int, str]] = []

    async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path:
        self.downloaded_urls.append(url)
        if len(self.downloaded_urls) == 1:
            raise CentralWorkerError("signed download URL expired", status_code=403)
        destination.write_bytes(b"video")
        return destination

    async def fetch_target(self, job_id: int, claim_token: str) -> RecordingAnalysisTarget:
        self.fetches.append((job_id, claim_token))
        return self.refreshed_target


def _claim_data(*, duplicate: bool = False) -> dict[str, object]:
    return {
        "jobId": 71,
        "status": "RUNNING",
        "attempt": 1,
        "duplicate": duplicate,
        "startedAt": "2026-07-30T00:00:00Z",
        "claimedBy": "recording-ai-worker",
        "claimExpiresAt": "2026-07-30T00:05:00Z",
        "leaseToken": None if duplicate else "lease-1",
    }


def _target_data() -> dict[str, object]:
    return {
        "jobId": 71,
        "caseId": 11,
        "searchConditionId": 21,
        "recordingId": 31,
        "cameraId": 41,
        "cameraCode": "CAM-001",
        "cameraName": "Gate A",
        "recordingObjectKey": "recordings/CAM-001/video.mp4",
        "recordingDownloadUrl": "https://storage.example/video.mp4",
        "recordingStart": "2026-07-30T00:00:00Z",
        "recordingEnd": "2026-07-30T01:00:00Z",
        "prompt": "red jacket",
        "exclusionPrompt": None,
        "searchStart": "2026-07-30T00:00:00Z",
        "searchEnd": "2026-07-30T00:05:00Z",
        "searchArea": "front gate",
        "searchFromMs": 0,
        "searchToMs": 5_000,
        "attempt": 1,
    }


def _envelope(data: dict[str, object]) -> dict[str, object]:
    return {"timestamp": "2026-07-30T00:00:00Z", "data": data}


def test_notebook_worker_claims_downloads_infers_uploads_and_completes(tmp_path: Path) -> None:
    state: dict[str, object] = {
        "completed": None,
        "heartbeat": False,
        "failed": False,
        "uploads": [],
    }

    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.host == "central.example":
            assert request.headers["X-Worker-Key"] == "test-key"
            assert "X-AI-Worker-Key" not in request.headers
        else:
            assert "X-Worker-Key" not in request.headers
        if request.url.path == "/api/v1/internal/recording-analysis-jobs/71/claim":
            assert request.method == "POST"
            assert request.content == b""
            return httpx2.Response(200, json=_envelope(_claim_data()), request=request)
        if request.url.path == "/api/v1/internal/recording-analysis-jobs/71/target":
            assert request.headers["X-Worker-Claim-Token"] == "lease-1"
            return httpx2.Response(200, json=_envelope(_target_data()), request=request)
        if request.url.path == "/api/v1/internal/recording-analysis-jobs/71/heartbeat":
            assert request.headers["X-Worker-Claim-Token"] == "lease-1"
            state["heartbeat"] = True
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "jobId": 71,
                        "status": "RUNNING",
                        "claimExpiresAt": "2026-07-30T00:10:00Z",
                    }
                ),
                request=request,
            )
        if request.url.path == "/api/v1/internal/recording-analysis-jobs/71/upload-urls":
            assert request.headers["X-Worker-Claim-Token"] == "lease-1"
            assert json.loads(request.content) == {
                "candidates": [
                    {
                        "trackId": "track-3",
                        "frameContentType": "image/jpeg",
                        "cropContentType": "image/jpeg",
                    }
                ]
            }
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "attempt": 1,
                        "candidates": [
                            {
                                "trackId": "track-3",
                                "frame": {
                                    "objectKey": "analysis/analysis-71/attempt-1/frames/frame.jpg",
                                    "uploadUrl": "https://storage.example/upload/frame.jpg",
                                    "contentType": "image/jpeg",
                                },
                                "crop": {
                                    "objectKey": "analysis/analysis-71/attempt-1/crops/crop.jpg",
                                    "uploadUrl": "https://storage.example/upload/crop.jpg",
                                    "contentType": "image/jpeg",
                                },
                            }
                        ],
                        "expiresInSeconds": 900,
                    }
                ),
                request=request,
            )
        if request.url.path in {"/upload/frame.jpg", "/upload/crop.jpg"}:
            uploads = state["uploads"]
            assert isinstance(uploads, list)
            uploads.append((request.url.path, request.content, request.headers["Content-Type"]))
            return httpx2.Response(200, request=request)
        if request.url.path == "/api/v1/internal/recording-analysis-jobs/71/result":
            assert request.headers["X-Worker-Claim-Token"] == "lease-1"
            payload = json.loads(request.content)
            assert payload["resultId"] == "notebook-test:71:1"
            assert payload["candidates"][0]["detectedAt"] == "2026-07-30T00:00:01.250000Z"
            assert "cropPath" not in request.content.decode("utf-8")
            state["completed"] = payload
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "jobId": 71,
                        "resultId": "notebook-test:71:1",
                        "status": "SUCCEEDED",
                        "candidateCount": 1,
                        "candidateIds": [9001],
                        "duplicate": False,
                        "completedAt": "2026-07-30T00:00:01Z",
                    }
                ),
                request=request,
            )
        if request.url.path == "/video.mp4":
            return httpx2.Response(200, content=b"video", request=request)
        state["failed"] = True
        return httpx2.Response(404, request=request)

    async def scenario() -> None:
        transport = httpx2.MockTransport(handler)
        async with httpx2.AsyncClient(
            transport=transport,
            base_url="https://central.example",
        ) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                client=http_client,
            )
            settings = NotebookWorkerSettings(
                central_api_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                model_key="fixture-hybrid-v1",
                heartbeat_interval_seconds=0.51,
                cache_dir=tmp_path / "cache",
                output_dir=tmp_path / "output",
            )
            engine = FixtureEngine()
            worker = NotebookWorker(settings, engine_factory=lambda: engine)
            claim = await client.claim_job(71)
            assert await worker.process_claim(client, claim) is True
            assert engine.similarity_threshold is None

    anyio.run(scenario)

    assert state["completed"] is not None
    assert state["heartbeat"] is True
    assert state["failed"] is False
    assert state["uploads"] == [
        ("/upload/frame.jpg", b"frame", "image/jpeg"),
        ("/upload/crop.jpg", b"crop", "image/jpeg"),
    ]


def test_notebook_worker_reports_failure_when_target_lookup_fails(tmp_path: Path) -> None:
    calls: list[str] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        if request.url.path.endswith("/claim"):
            return httpx2.Response(200, json=_envelope(_claim_data()), request=request)
        if request.url.path.endswith("/target"):
            return httpx2.Response(
                503,
                json={"code": "STORAGE_UNAVAILABLE", "message": "storage unavailable"},
                request=request,
            )
        if request.url.path.endswith("/fail"):
            payload = json.loads(request.content)
            assert payload["resultId"] == "notebook-test:71:1:failure"
            assert payload["errorCode"] == "CentralWorkerError"
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "jobId": 71,
                        "resultId": "notebook-test:71:1:failure",
                        "status": "FAILED",
                        "attempt": 1,
                        "duplicate": False,
                        "completedAt": "2026-07-30T00:00:01Z",
                    }
                ),
                request=request,
            )
        return httpx2.Response(404, request=request)

    async def scenario() -> None:
        transport = httpx2.MockTransport(handler)
        async with httpx2.AsyncClient(
            transport=transport, base_url="https://central.example"
        ) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                client=http_client,
            )
            worker = NotebookWorker(
                NotebookWorkerSettings(
                    central_api_url="https://central.example",
                    api_key="test-key",
                    worker_id="notebook-test",
                    cache_dir=tmp_path / "cache",
                    output_dir=tmp_path / "output",
                ),
                engine_factory=FixtureEngine,
            )
            claim = await client.claim_job(71)
            assert await worker.process_claim(client, claim) is True

    anyio.run(scenario)

    assert calls == [
        "/api/v1/internal/recording-analysis-jobs/71/claim",
        "/api/v1/internal/recording-analysis-jobs/71/target",
        "/api/v1/internal/recording-analysis-jobs/71/fail",
    ]


def test_notebook_worker_refreshes_an_expired_signed_recording_url_once(tmp_path: Path) -> None:
    async def scenario() -> None:
        initial_data = _target_data()
        refreshed_data = _target_data()
        refreshed_data["recordingDownloadUrl"] = "https://storage.example/video-refreshed.mp4"
        initial_target = RecordingAnalysisTarget.model_validate(initial_data)
        refreshed_target = RecordingAnalysisTarget.model_validate(refreshed_data)
        client = RefreshingDownloadClient(refreshed_target)
        worker = NotebookWorker(
            NotebookWorkerSettings(
                central_api_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                cache_dir=tmp_path / "cache",
                output_dir=tmp_path / "output",
            ),
            engine_factory=FixtureEngine,
        )
        worker.settings.cache_dir.mkdir(parents=True)

        target, video_path = await worker._download_target_recording(  # type: ignore[arg-type]
            client,
            initial_target,
            "lease-1",
        )

        assert target.recording_download_url == "https://storage.example/video-refreshed.mp4"
        assert video_path.read_bytes() == b"video"
        assert client.fetches == [(71, "lease-1")]
        assert client.downloaded_urls == [
            "https://storage.example/video.mp4",
            "https://storage.example/video-refreshed.mp4",
        ]

    anyio.run(scenario)


def test_notebook_worker_loads_candidate_engine_environment_from_dotenv(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / ".env").write_text("QWEN_CANDIDATE_DEVICE=cpu\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QWEN_CANDIDATE_DEVICE", raising=False)
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="test-key",
        worker_id="notebook-test",
    )

    NotebookWorker(settings, engine_factory=FixtureEngine)

    assert os.environ["QWEN_CANDIDATE_DEVICE"] == "cpu"


def test_notebook_worker_settings_rejects_placeholder_api_key() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        NotebookWorkerSettings(
            central_api_url="https://central.example",
            api_key="inject-from-local-secret-store",
        )


def test_notebook_worker_settings_accepts_central_server_env_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CENTRAL_API_BASE_URL", "https://central.example")
    monkeypatch.setenv("CENTRAL_API_WORKER_KEY", "test-key")
    monkeypatch.setenv("RABBITMQ_QUEUE", "legacy.recording.queue")

    settings = NotebookWorkerSettings()

    assert settings.central_api_url == "https://central.example"
    assert settings.api_key.get_secret_value() == "test-key"
    assert settings.rabbitmq_queue == "legacy.recording.queue"


def test_notebook_worker_loads_an_explicit_env_file_before_settings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    env_file = tmp_path / "ai.env.txt"
    env_file.write_text(
        "\n".join(
            (
                "CENTRAL_API_BASE_URL=https://central.example",
                "CENTRAL_API_WORKER_KEY=test-key",
                "RABBITMQ_URL=amqps://worker:secret@broker.example/%2Feyesonu",
                "RABBITMQ_QUEUE=search.target.recording.queue",
            )
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    for key in (
        "CENTRAL_API_BASE_URL",
        "CENTRAL_API_WORKER_KEY",
        "RABBITMQ_URL",
        "RABBITMQ_QUEUE",
        "EYESONU_AI_WORKER_CENTRAL_API_URL",
        "EYESONU_AI_WORKER_API_KEY",
        "EYESONU_AI_WORKER_RABBITMQ_URL",
        "EYESONU_AI_WORKER_RABBITMQ_QUEUE",
    ):
        monkeypatch.delenv(key, raising=False)

    _load_worker_env_file(env_file)
    settings = NotebookWorkerSettings()

    assert settings.central_api_url == "https://central.example"
    assert settings.api_key.get_secret_value() == "test-key"
    assert settings.rabbitmq_url is not None
    assert settings.rabbitmq_queue == "search.target.recording.queue"
