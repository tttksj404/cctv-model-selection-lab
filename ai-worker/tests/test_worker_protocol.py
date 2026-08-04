import json
from datetime import UTC, datetime, timedelta
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
    RecordingAnalysisClaim,
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisTarget,
    RecordingAnalysisUploadObject,
    result_from_runtime,
)


def _target(
    *, recording_duration_seconds: int = 3_600, search_to_ms: int = 5_000
) -> RecordingAnalysisTarget:
    return RecordingAnalysisTarget(
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        cameraId=41,
        cameraCode="CAM-001",
        cameraName="Gate A",
        recordingObjectKey="recordings/CAM-001/video.mp4",
        recordingDownloadUrl="https://storage.example/video.mp4",
        recordingStart=datetime(2026, 7, 30, tzinfo=UTC),
        recordingEnd=datetime(2026, 7, 30, tzinfo=UTC)
        + timedelta(seconds=recording_duration_seconds),
        prompt="red jacket",
        searchFromMs=0,
        searchToMs=search_to_ms,
        attempt=1,
    )


@pytest.mark.parametrize(
    ("recording_duration_seconds", "search_to_ms"),
    ((30, 30_000), (60, 60_000)),
)
def test_target_accepts_closed_30_or_60_second_recording_windows(
    recording_duration_seconds: int, search_to_ms: int
) -> None:
    target = _target(
        recording_duration_seconds=recording_duration_seconds,
        search_to_ms=search_to_ms,
    )

    assert target.recording_end - target.recording_start == timedelta(
        seconds=recording_duration_seconds
    )
    assert target.search_to_ms == search_to_ms


def _envelope(data: dict[str, object]) -> dict[str, object]:
    return {"timestamp": "2026-07-30T00:00:00Z", "data": data}


def test_result_uses_absolute_detection_time_and_never_serializes_local_paths() -> None:
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
    upload = RecordingAnalysisEvidenceUpload(
        trackId="track-3",
        frame=RecordingAnalysisUploadObject(
            objectKey="analysis/analysis-71/attempt-1/frames/frame.jpg",
            uploadUrl="https://storage.example/upload/frame.jpg",
            contentType="image/jpeg",
        ),
        crop=RecordingAnalysisUploadObject(
            objectKey="analysis/analysis-71/attempt-1/crops/crop.jpg",
            uploadUrl="https://storage.example/upload/crop.jpg",
            contentType="image/jpeg",
        ),
    )

    result = result_from_runtime(
        runtime,
        _target(),
        worker_id="notebook-test",
        evidence_by_track_id={"track-3": upload},
    )

    assert result.result_id == "notebook-test:71:1"
    assert result.candidates[0].detected_at == datetime(2026, 7, 30, 0, 0, 1, 250_000, tzinfo=UTC)
    payload = result.model_dump(mode="json", by_alias=True)
    assert "cropPath" not in str(payload)
    assert "framePath" not in str(payload)
    assert payload["candidates"][0]["boundingBox"] == {
        "x": 10,
        "y": 20,
        "width": 30,
        "height": 40,
    }


def test_non_duplicate_claim_requires_lease_token() -> None:
    with pytest.raises(ValidationError, match="leaseToken"):
        RecordingAnalysisClaim(
            jobId=71,
            status="RUNNING",
            attempt=1,
            duplicate=False,
            startedAt=datetime(2026, 7, 30, tzinfo=UTC),
            claimedBy="recording-ai-worker",
            claimExpiresAt=datetime(2026, 7, 30, 0, 5, tzinfo=UTC),
        )


def test_rabbit_event_matches_current_dev_payload_without_person_data() -> None:
    event = RabbitWorkerJobEvent(
        commandId="command-71",
        eventType="RECORDING_ANALYSIS_JOB_CREATED",
        jobId=71,
        caseId=11,
        recordingId=31,
        cameraId=41,
        cameraCode="CAM-001",
        cameraName="Gate A",
        recordingObjectKey="recordings/CAM-001/video.mp4",
        attempt=1,
        occurredAt=datetime(2026, 7, 30, tzinfo=UTC),
    )

    assert event.job_id == 71
    assert (
        event.model_dump(mode="json", by_alias=True)["eventType"]
        == "RECORDING_ANALYSIS_JOB_CREATED"
    )


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


def test_central_client_chunks_upload_url_requests_without_reusing_track_ids() -> None:
    async def scenario() -> None:
        requested_track_counts: list[int] = []

        async def handler(request: httpx2.Request) -> httpx2.Response:
            assert request.headers["X-Worker-Key"] == "test-key"
            assert request.headers["X-Worker-Claim-Token"] == "lease-1"
            payload = json.loads(request.content)
            candidates = payload["candidates"]
            requested_track_counts.append(len(candidates))
            response_candidates = [
                {
                    "trackId": candidate["trackId"],
                    "frame": {
                        "objectKey": f"analysis/frames/{candidate['trackId']}.jpg",
                        "uploadUrl": f"https://storage.example/frames/{candidate['trackId']}.jpg",
                        "contentType": "image/jpeg",
                    },
                    "crop": {
                        "objectKey": f"analysis/crops/{candidate['trackId']}.jpg",
                        "uploadUrl": f"https://storage.example/crops/{candidate['trackId']}.jpg",
                        "contentType": "image/jpeg",
                    },
                }
                for candidate in candidates
            ]
            return httpx2.Response(
                200,
                json=_envelope(
                    {
                        "attempt": 1,
                        "candidates": response_candidates,
                        "expiresInSeconds": 900,
                    }
                ),
                request=request,
            )

        runtime_candidates = tuple(
            RuntimeCandidate(
                candidateKey=f"track-{index}",
                frameOffsetMs=index,
                similarity=0.9,
                framePath=Path(f"frame-{index}.jpg"),
                cropPath=Path(f"crop-{index}.jpg"),
                boundingBox=RuntimeBoundingBox(x=0, y=0, width=1, height=1),
            )
            for index in range(101)
        )
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
            uploads = await client.create_evidence_upload_urls(71, "lease-1", runtime_candidates)

        assert requested_track_counts == [100, 1]
        assert set(uploads) == {candidate.candidate_key for candidate in runtime_candidates}

    anyio.run(scenario)
