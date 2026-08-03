from __future__ import annotations

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
from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.notebook_worker import NotebookWorker, NotebookWorkerSettings


class FixtureEngine:
    model_key = "fixture-hybrid-v1"

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        time.sleep(0.7)
        crop_path = request.output_dir / "track-3.jpg"
        crop_path.write_bytes(b"crop")
        return CandidateRuntimeResponse(
            modelKey=self.model_key,
            candidates=(
                RuntimeCandidate(
                    candidateKey="track-3",
                    frameOffsetMs=1_250,
                    similarity=0.91,
                    cropPath=crop_path,
                    boundingBox=RuntimeBoundingBox(x=10, y=20, width=30, height=40),
                    attributeSummary="fixture",
                ),
            ),
        )


def test_notebook_worker_claims_downloads_infers_and_completes(tmp_path: Path) -> None:
    state: dict[str, object] = {"completed": None, "heartbeat": False, "failed": False}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        if request.url.path == "/api/v1/ai-worker/jobs/claim":
            return httpx2.Response(
                200,
                json={
                    "timestamp": "2026-07-30T00:00:00Z",
                    "data": {
                        "schemaVersion": "eyesonu-ai-worker-v1",
                        "job": {
                            "schemaVersion": "eyesonu-ai-worker-v1",
                            "jobId": 71,
                            "caseId": 11,
                            "searchConditionId": 21,
                            "recordingId": 31,
                            "modelKey": "fixture-hybrid-v1",
                            "cameraId": 41,
                            "cameraName": "Gate A",
                            "cameraAddress": "CAM-001",
                            "videoUrl": "https://storage.example/video.mp4",
                            "recordingStart": "2026-07-30T00:00:00Z",
                            "recordingEnd": "2026-07-30T01:00:00Z",
                            "prompt": "red jacket",
                            "similarityThreshold": 0.8,
                            "searchFromMs": 0,
                            "searchToMs": 5_000,
                            "leaseExpiresAt": "2026-07-30T00:01:00Z",
                        },
                        "leaseToken": "lease-1",
                        "leaseExpiresAt": "2026-07-30T00:01:00Z",
                        "pollAfterMs": 0,
                    },
                },
                request=request,
            )
        if request.url.path == "/api/v1/ai-worker/jobs/71/complete":
            decoded = request.content.decode("utf-8")
            assert "cropPath" not in decoded
            assert "frameOffsetMs" in decoded
            state["completed"] = decoded
            return httpx2.Response(
                200,
                json={
                    "timestamp": "2026-07-30T00:00:01Z",
                    "data": {
                        "schemaVersion": "eyesonu-ai-worker-v1",
                        "jobId": 71,
                        "status": "SUCCEEDED",
                        "workerId": "notebook-test",
                        "resultModelKey": "fixture-hybrid-v1",
                        "resultDigest": "server-digest",
                    },
                },
                request=request,
            )
        if request.url.path == "/api/v1/ai-worker/jobs/71/heartbeat":
            state["heartbeat"] = True
            return httpx2.Response(
                200,
                json={
                    "timestamp": "2026-07-30T00:00:01Z",
                    "data": {
                        "schemaVersion": "eyesonu-ai-worker-v1",
                        "jobId": 71,
                        "status": "RUNNING",
                        "leaseExpiresAt": "2026-07-30T00:02:00Z",
                    },
                },
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
            worker = NotebookWorker(settings, engine_factory=lambda: FixtureEngine())
            assert await worker._run_once(client) is True

    anyio.run(scenario)

    assert state["completed"] is not None
    assert state["heartbeat"] is True
    assert state["failed"] is False


def test_notebook_worker_loads_candidate_engine_environment_from_dotenv(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / ".env").write_text("QWEN_CANDIDATE_DEVICE=cpu\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QWEN_CANDIDATE_DEVICE", raising=False)
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="test-key",
        worker_id="notebook-test",
    )

    NotebookWorker(settings, engine_factory=lambda: FixtureEngine())

    assert os.environ["QWEN_CANDIDATE_DEVICE"] == "cpu"


def test_notebook_worker_settings_rejects_placeholder_api_key() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        NotebookWorkerSettings(
            central_api_url="https://central.example",
            api_key="inject-from-local-secret-store",
        )


@pytest.mark.parametrize("central_api_url", ["central.example", "file:///tmp/worker"])
def test_notebook_worker_settings_requires_http_central_api_url(central_api_url: str) -> None:
    with pytest.raises(ValueError, match="http or https"):
        NotebookWorkerSettings(
            central_api_url=central_api_url,
            api_key="test-key",
        )
