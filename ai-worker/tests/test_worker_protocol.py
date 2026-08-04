from datetime import UTC, datetime
from pathlib import Path

import anyio
import httpx2
import pytest
from pydantic import ValidationError

from qwen_backend.candidate_runtime import (
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.central_client import (
    CentralClientOptions,
    CentralWorkerClient,
    CentralWorkerError,
)
from qwen_backend.worker_protocol import (
    RabbitWorkerJobEvent,
    WorkerClaimResponse,
    WorkerJob,
    worker_result_from_runtime,
)


def test_runtime_result_never_serializes_notebook_absolute_crop_path() -> None:
    runtime = CandidateRuntimeResponse(
        modelKey="fixture-hybrid-v1",
        candidates=(
            RuntimeCandidate(
                candidateKey="track-3",
                frameOffsetMs=1_250,
                similarity=0.91,
                framePath="C:/Users/worker/artifacts/job-71/frame-1250.jpg",
                cropPath="C:/Users/worker/artifacts/job-71/track-3.jpg",
                boundingBox=RuntimeBoundingBox(x=10, y=20, width=30, height=40),
                attributeSummary="fixture",
            ),
        ),
    )

    result = worker_result_from_runtime(runtime, 42)

    payload = result.model_dump(by_alias=True)
    assert "cropPath" not in payload["candidates"][0]
    assert payload["candidates"][0]["boundingBox"] == {
        "x": 10,
        "y": 20,
        "width": 30,
        "height": 40,
    }


def test_claim_response_requires_lease_with_job() -> None:
    job = WorkerJob(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        modelKey="fixture-hybrid-v1",
        cameraId=41,
        cameraName="Gate A",
        cameraAddress="CAM-001",
        videoUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        similarityThreshold=0.8,
        searchFromMs=0,
        searchToMs=5_000,
        leaseExpiresAt=datetime(2026, 7, 30, 0, 1, tzinfo=UTC),
    )

    response = WorkerClaimResponse(
        job=job,
        leaseToken="lease-1",
        leaseExpiresAt=job.lease_expires_at,
    )

    assert response.job is not None
    assert response.lease_token == "lease-1"


def test_claim_job_accepts_server_contract_without_similarity_threshold() -> None:
    job = WorkerJob(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        modelKey="fixture-hybrid-v1",
        cameraId=41,
        cameraName="Gate A",
        cameraAddress="CAM-001",
        videoUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, 1, tzinfo=UTC),
        prompt="red jacket",
        searchFromMs=0,
        searchToMs=5_000,
        leaseExpiresAt=datetime(2026, 7, 30, 0, 1, tzinfo=UTC),
    )

    assert job.similarity_threshold is None


def test_rabbit_worker_event_contains_only_routing_metadata() -> None:
    event = RabbitWorkerJobEvent(
        eventId="command-71",
        jobId=71,
        caseId=11,
        attempt=1,
        occurredAt=datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert event.job_id == 71
    assert event.model_dump(mode="json", by_alias=True) == {
        "schemaVersion": "eyesonu-ai-worker-event-v1",
        "eventId": "command-71",
        "jobId": 71,
        "caseId": 11,
        "attempt": 1,
        "occurredAt": "2026-07-30T00:00:00Z",
    }


def test_central_client_does_not_retry_mutating_requests_by_default() -> None:
    options = CentralClientOptions()

    assert options.transport_retries == 0
    assert options.request_timeout().read == 30.0


def test_central_client_rejects_inconsistent_connection_limits() -> None:
    with pytest.raises(ValidationError, match="keepalive"):
        CentralClientOptions(max_connections=2, max_keepalive_connections=3)


def test_central_client_rejects_url_without_host() -> None:
    with pytest.raises(ValueError, match="central API URL"):
        CentralWorkerClient(
            base_url="https://",
            api_key="test-key",
            worker_id="notebook-test",
        )


def test_central_client_rejects_placeholder_api_key() -> None:
    with pytest.raises(ValueError, match="placeholder"):
        CentralWorkerClient(
            base_url="https://central.example",
            api_key="inject-from-local-secret-store",
            worker_id="notebook-test",
        )


def test_central_client_rejects_malformed_storage_content_length(tmp_path: Path) -> None:
    async def scenario() -> None:
        async def handler(request: httpx2.Request) -> httpx2.Response:
            return httpx2.Response(
                200,
                headers={"content-length": "not-a-number"},
                content=b"video",
                request=request,
            )

        transport = httpx2.MockTransport(handler)
        async with httpx2.AsyncClient(transport=transport) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key="test-key",
                worker_id="notebook-test",
                client=http_client,
            )
            with pytest.raises(CentralWorkerError, match="invalid content length"):
                await client.download(
                    "https://storage.example/video.mp4",
                    tmp_path / "video.mp4",
                    max_bytes=1024,
                )

    anyio.run(scenario)
