from __future__ import annotations

import json
from datetime import UTC, datetime

import anyio
import httpx2

from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.object_storage import S3ObjectStore, S3ObjectStoreConfig
from qwen_backend.rabbit_worker import RabbitJobProcessor
from qwen_backend.worker_protocol import (
    DeviceCandidateEvent,
    RabbitWorkerJobEvent,
)

DEVICE_KEY = <redacted>


class FakeDelivery:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers: dict[str, object] = {}
        self.acked = 0
        self.rejected: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        assert multiple is False
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)


class FakeRetryScheduler:
    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        raise AssertionError("device-mode success must not schedule a retry")


class DeviceClientWithoutClaim:
    uses_device_key = True


class DeviceWorker:
    def __init__(self) -> None:
        self.events: list[RabbitWorkerJobEvent] = []

    async def process_device_event(
        self,
        client: DeviceClientWithoutClaim,
        event: RabbitWorkerJobEvent,
    ) -> bool:
        self.events.append(event)
        return True


def _event(*, enriched: bool = True) -> RabbitWorkerJobEvent:
    payload: dict[str, object] = {
        "commandId": "command-71",
        "eventType": "RECORDING_ANALYSIS_JOB_CREATED",
        "jobId": 71,
        "occurredAt": "2026-07-30T00:00:00Z",
    }
    if enriched:
        payload.update(
            {
                "caseId": 11,
                "recordingId": 31,
                "cameraId": 41,
                "cameraCode": "CAM-001",
                "cameraName": "Gate A",
                "recordingObjectKey": "recordings/CAM-001/video.mp4",
                "prompt": "gray shirt, black pants",
                "exclusionPrompt": "no person",
                "searchStart": "2026-07-30T00:00:00Z",
                "searchEnd": "2026-07-30T00:05:00Z",
                "searchArea": "front gate",
                "attempt": 1,
            }
        )
    return RabbitWorkerJobEvent.model_validate(payload)


def test_device_key_is_sent_as_device_key_to_device_result_endpoint() -> None:
    event = _event()
    candidate = DeviceCandidateEvent.from_runtime(
        event,
        track_id="track-3",
        similarity=0.91,
        frame_object_key="analysis/analysis-71/attempt-1/frames/track-3.jpg",
        crop_object_key="analysis/analysis-71/attempt-1/crops/track-3.jpg",
        detected_at=datetime(2026, 7, 30, 0, 0, 1, 250_000, tzinfo=UTC),
        x=10,
        y=20,
        width=30,
        height=40,
    )
    seen: dict[str, object] = {}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["device_key"] = request.headers.get("X-Device-Key")
        seen["worker_key"] = request.headers.get("X-Worker-Key")
        seen["payload"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={"timestamp": "2026-07-30T00:00:02Z", "data": {"job": {}}},
            request=request,
        )

    async def scenario() -> None:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler),
            base_url="https://central.example",
        ) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key=DEVICE_KEY,
                worker_id="notebook-test",
                client=http_client,
            )
            await client.complete_device_result(event.job_id, candidate)

    anyio.run(scenario)

    assert seen["path"] == "/api/v1/device/recording-analysis-jobs/71/result"
    assert seen["device_key"] == DEVICE_KEY
    assert seen["worker_key"] is None
    assert isinstance(seen["payload"], dict)
    assert seen["payload"]["cameraCode"] == "CAM-001"  # type: ignore[index]


def test_device_mode_routes_enriched_rabbit_event_without_internal_claim() -> None:
    worker = DeviceWorker()
    event = _event()
    delivery = FakeDelivery(event.model_dump_json(by_alias=True).encode())
    processor = RabbitJobProcessor(
        worker,  # type: ignore[arg-type]
        retry_scheduler=FakeRetryScheduler(),
        retry_delay_seconds=5.0,
        max_retry_attempts=3,
    )

    async def scenario() -> bool:
        return await processor.handle(delivery, DeviceClientWithoutClaim())  # type: ignore[arg-type]

    assert anyio.run(scenario) is True
    assert delivery.acked == 1
    assert delivery.rejected == []
    assert [item.job_id for item in worker.events] == [71]


def test_device_event_requires_enriched_recording_fields() -> None:
    event = _event(enriched=False)

    assert event.case_id is None
    assert event.recording_object_key is None
    assert event.prompt is None


def test_device_mode_dead_letters_event_without_camera_name() -> None:
    payload = _event().model_dump(mode="json", by_alias=True)
    payload.pop("cameraName")
    event = RabbitWorkerJobEvent.model_validate(payload)
    worker = DeviceWorker()
    delivery = FakeDelivery(event.model_dump_json(by_alias=True).encode())
    processor = RabbitJobProcessor(
        worker,  # type: ignore[arg-type]
        retry_scheduler=FakeRetryScheduler(),
        retry_delay_seconds=5.0,
        max_retry_attempts=3,
    )

    async def scenario() -> bool:
        return await processor.handle(delivery, DeviceClientWithoutClaim())  # type: ignore[arg-type]

    assert anyio.run(scenario) is False
    assert delivery.acked == 0
    assert delivery.rejected == [False]
    assert worker.events == []


def test_private_storage_signs_object_key_without_leaking_secret(tmp_path) -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen["host"] = request.headers.get("Host")
        seen["authorization"] = request.headers.get("Authorization")
        seen["secret"] = request.headers.get("x-amz-secret-key")
        return httpx2.Response(
            200,
            content=b"video",
            headers={"content-length": "5"},
            request=request,
        )

    async def scenario() -> None:
        async with httpx2.AsyncClient(transport=httpx2.MockTransport(handler)) as client:
            store = S3ObjectStore(
                S3ObjectStoreConfig(
                    endpoint="https://storage.example",
                    bucket="eyesonu-media",
                    region="ap-northeast-2",
                    access_key="worker-access",
                    secret_key="worker-secret",
                    path_style=False,
                ),
                client,
            )
            await store.download(
                "recordings/CAM-001/video.mp4",
                tmp_path / "video.mp4",
                max_bytes=100,
                chunk_bytes=64 * 1024,
            )

    anyio.run(scenario)

    assert (tmp_path / "video.mp4").read_bytes() == b"video"
    assert seen["host"] == "eyesonu-media.storage.example"
    assert isinstance(seen["authorization"], str)
    assert "Credential=worker-access/" in seen["authorization"]  # type: ignore[operator]
    assert "worker-secret" not in str(seen["authorization"])
    assert seen["secret"] is None

