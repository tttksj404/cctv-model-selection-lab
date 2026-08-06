from __future__ import annotations

import json
from pathlib import Path

import anyio
import httpx2
import pytest

from qwen_backend.candidate_runtime import CandidateRuntimeRequest, CandidateRuntimeResponse
from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.notebook_worker import NotebookWorker
from qwen_backend.worker_settings import NotebookWorkerSettings


class NoLeaseFixtureEngine:
    """Return an empty, valid inference result without requiring a real GPU model."""

    model_key = "fixture-hybrid-v1"

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        return CandidateRuntimeResponse(modelKey=self.model_key, candidates=())


def _envelope(data: dict[str, object]) -> dict[str, object]:
    return {"timestamp": "2026-08-06T00:00:00Z", "data": data}


def _current_controller_target() -> dict[str, object]:
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
        "recordingStart": "2026-08-06T00:00:00Z",
        "recordingEnd": "2026-08-06T00:01:00Z",
        "prompt": "gray shirt, black pants",
        "exclusionPrompt": None,
        "searchStart": "2026-08-06T00:00:00Z",
        "searchEnd": "2026-08-06T00:00:05Z",
        "searchArea": "front gate",
        "searchFromMs": 0,
        "searchToMs": 5_000,
        "attempt": 1,
    }


def test_notebook_worker_completes_current_controller_claim_without_lease_token(
    tmp_path: Path,
) -> None:
    """The deployed RecordingAnalysisWorkerController uses worker ownership, not lease tokens."""

    calls: list[str] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        calls.append(request.url.path)
        if request.url.host == "central.example":
            assert request.headers["X-Worker-Key"] == "test-key"
            assert "X-Worker-Claim-Token" not in request.headers

        if request.url.path.endswith("/claim"):
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "jobId": 71,
                        "status": "RUNNING",
                        "attempt": 1,
                        "duplicate": False,
                        "startedAt": "2026-08-06T00:00:00Z",
                        "claimedBy": "notebook-test",
                        "claimExpiresAt": "2026-08-06T00:05:00Z",
                    }
                ),
                request=request,
            )
        if request.url.path.endswith("/target"):
            return httpx2.Response(
                200,
                json=_envelope(_current_controller_target()),
                request=request,
            )
        if request.url.path == "/video.mp4":
            return httpx2.Response(200, content=b"video", request=request)
        if request.url.path.endswith("/result"):
            payload = json.loads(request.content)
            assert payload["resultId"] == "notebook-test:71:1"
            assert payload["candidates"] == []
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "jobId": 71,
                        "resultId": "notebook-test:71:1",
                        "status": "SUCCEEDED",
                        "candidateCount": 0,
                        "candidateIds": [],
                        "duplicate": False,
                        "completedAt": "2026-08-06T00:00:01Z",
                    }
                ),
                request=request,
            )
        raise AssertionError(f"unexpected worker request: {request.url}")

    async def scenario() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler),
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
                cache_dir=tmp_path / "cache",
                output_dir=tmp_path / "output",
                download_window_mode="analyze",
            )
            worker = NotebookWorker(settings, engine_factory=NoLeaseFixtureEngine)

            claim = await client.claim_job(71)

            assert await worker.process_claim(client, claim) is True

    anyio.run(scenario)

    assert calls == [
        "/api/v1/internal/recording-analysis-jobs/71/claim",
        "/api/v1/internal/recording-analysis-jobs/71/target",
        "/video.mp4",
        "/api/v1/internal/recording-analysis-jobs/71/result",
    ]


def test_claim_schema_failure_logs_wire_fields_before_propagating(
    caplog,
) -> None:
    async def handler(request: httpx2.Request) -> httpx2.Response:
        return httpx2.Response(
            200,
            json=_envelope(
                {
                    "jobId": 71,
                    "status": "RUNNING",
                    "attempt": 1,
                    "duplicate": False,
                    "startedAt": "not-an-iso-timestamp",
                }
            ),
            request=request,
        )

    async def scenario() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler),
            base_url="https://central.example",
        ) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                auth_mode="worker",
                client=http_client,
            )
            await client.claim_job(71)

    with caplog.at_level("ERROR", logger="qwen_backend.central_client"):
        with pytest.raises(ValueError):
            anyio.run(scenario)

    assert "claim response schema failed job_id=71" in caplog.text
    assert "jobId" in caplog.text
    assert "startedAt" in caplog.text
