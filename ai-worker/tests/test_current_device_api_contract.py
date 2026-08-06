from __future__ import annotations

import json
from datetime import UTC, datetime

import anyio
import httpx2

from qwen_backend.central_client import CentralWorkerClient
from qwen_backend.rabbit_worker import RabbitJobProcessor
from qwen_backend.worker_protocol import (
    DeviceAiCompleteCandidate,
    DeviceAiCompleteRequest,
    DeviceAiFailureRequest,
    DeviceAiSearchJob,
    DeviceBoundingBox,
    RabbitWorkerJobEvent,
)
from qwen_backend.worker_settings import NotebookWorkerSettings

DEVICE_KEY = "msk_0123456789abcdef." + "a" * 64


def _job(job_id: int = 71) -> DeviceAiSearchJob:
    return DeviceAiSearchJob(
        job_id=job_id,
        lease_token="11111111-1111-4111-8111-111111111111",
        case_id=11,
        search_condition_id=21,
        recording_id=31,
        camera_id=41,
        camera_name="Gate A",
        camera_address="front gate",
        recording_object_key="recordings/gate-a/video.mp4",
        reference_photo_object_key="cases/11/reference.jpg",
        recording_start=datetime(2026, 7, 30, tzinfo=UTC),
        recording_end=datetime(2026, 7, 30, 0, 5, tzinfo=UTC),
        prompt="gray shirt, black pants",
    )


def test_current_device_claim_uses_device_header_and_claim_route() -> None:
    seen: dict[str, object] = {}

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen["path"] = request.url.path
        seen["device_key"] = request.headers.get("X-Device-Key")
        seen["worker_key"] = request.headers.get("X-Worker-Key")
        seen["body"] = json.loads(request.content)
        return httpx2.Response(
            200,
            json={
                "timestamp": "2026-07-30T00:00:00Z",
                "data": _job().model_dump(mode="json", by_alias=True),
            },
            request=request,
        )

    async def scenario() -> DeviceAiSearchJob | None:
        async with httpx2.AsyncClient(
            transport=httpx2.MockTransport(handler),
            base_url="https://central.example",
        ) as http_client:
            client = CentralWorkerClient(
                base_url="https://central.example",
                api_key=DEVICE_KEY,
                worker_id="notebook-test",
                auth_mode="device",
                client=http_client,
            )
            return await client.claim_device_job("hybrid-solider-clip-v1")

    claimed = anyio.run(scenario)

    assert claimed is not None
    assert claimed.job_id == 71
    assert seen["path"] == "/api/v1/device/ai/jobs/claim"
    assert seen["device_key"] == DEVICE_KEY
    assert seen["worker_key"] is None
    assert seen["body"] == {"modelKey": "hybrid-solider-clip-v1"}


def test_current_device_complete_payload_matches_backend_contract() -> None:
    request = DeviceAiCompleteRequest(
        lease_token="11111111-1111-4111-8111-111111111111",
        model_key="hybrid-solider-clip-v1",
        candidates=(
            DeviceAiCompleteCandidate(
                candidate_key="track-1",
                frame_offset_ms=1250,
                similarity=0.91,
                crop_object_key="ai-results/71/crops/track-1.jpg",
                clip_object_key="ai-results/71/frames/track-1.jpg",
                bounding_box=DeviceBoundingBox(x=10, y=20, width=30, height=40),
                attribute_summary="gray shirt, black pants",
            ),
        ),
    )

    payload = request.model_dump(mode="json", by_alias=True)

    assert payload == {
        "leaseToken": "11111111-1111-4111-8111-111111111111",
        "modelKey": "hybrid-solider-clip-v1",
        "candidates": [
            {
                "candidateKey": "track-1",
                "frameOffsetMs": 1250,
                "similarity": 0.91,
                "cropObjectKey": "ai-results/71/crops/track-1.jpg",
                "clipObjectKey": "ai-results/71/frames/track-1.jpg",
                "boundingBox": {"x": 10, "y": 20, "width": 30, "height": 40},
                "attributeSummary": "gray shirt, black pants",
            }
        ],
    }


def test_current_device_lease_and_terminal_callbacks_use_device_api_routes() -> None:
    seen: list[tuple[str, dict[str, object]]] = []

    async def handler(request: httpx2.Request) -> httpx2.Response:
        seen.append((request.url.path, json.loads(request.content or b"{}")))
        assert request.headers["X-Device-Key"] == DEVICE_KEY
        assert "X-Worker-Key" not in request.headers
        if request.url.path.endswith("/heartbeat"):
            return httpx2.Response(204, request=request)
        status = "SUCCEEDED" if request.url.path.endswith("/complete") else "FAILED"
        return httpx2.Response(
            200,
            json={
                "timestamp": "2026-07-30T00:00:00Z",
                "data": {"jobId": 71, "status": status, "resultCount": 0},
            },
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
                auth_mode="device",
                client=http_client,
            )
            await client.heartbeat_device_job(71, "11111111-1111-4111-8111-111111111111")
            await client.complete_device_job(
                71,
                DeviceAiCompleteRequest(
                    lease_token="11111111-1111-4111-8111-111111111111",
                    model_key="hybrid-solider-clip-v1",
                    candidates=(),
                ),
            )
            await client.fail_device_job(
                71,
                DeviceAiFailureRequest(
                    lease_token="11111111-1111-4111-8111-111111111111",
                    error_code="RuntimeError",
                    error_message="inference failed",
                    retryable=True,
                ),
            )

    anyio.run(scenario)

    assert [path for path, _ in seen] == [
        "/api/v1/device/ai/jobs/71/heartbeat",
        "/api/v1/device/ai/jobs/71/complete",
        "/api/v1/device/ai/jobs/71/fail",
    ]
    assert seen[0][1] == {"leaseToken": "11111111-1111-4111-8111-111111111111"}
    assert seen[1][1]["modelKey"] == "hybrid-solider-clip-v1"
    assert seen[2][1]["retryable"] is True


def test_settings_can_select_device_transport_explicitly(
    tmp_path,
    monkeypatch,
) -> None:
    env_file = tmp_path / "worker.env"
    env_file.write_text(
        "\n".join(
            (
                "CENTRAL_API_BASE_URL=https://central.example",
                f"CENTRAL_API_WORKER_KEY={DEVICE_KEY}",
                "AI_WORKER_AUTH_MODE=device",
            )
        ),
        encoding="utf-8",
    )

    for name in (
        "EYESONU_AI_WORKER_API_KEY",
        "X-Worker-Key",
        "CENTRAL_API_WORKER_KEY",
        "AI_WORKER_DEVICE_KEY",
        "EYESONU_AI_DEVICE_KEY",
        "AI_WORKER_AUTH_MODE",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = NotebookWorkerSettings(_env_file=env_file)

    assert settings.api_key.get_secret_value() == DEVICE_KEY
    assert settings.auth_mode == "device"


class _Delivery:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.headers: dict[str, object] = {}
        self.acked = 0
        self.rejected: list[bool] = []

    async def ack(self, multiple: bool = False) -> None:
        self.acked += 1

    async def reject(self, requeue: bool = False) -> None:
        self.rejected.append(requeue)


class _RetryScheduler:
    async def schedule(self, body: bytes, *, retry_count: int, delay_seconds: float) -> None:
        raise AssertionError("current device success must not schedule a retry")


class _CurrentDeviceClient:
    uses_current_device_api = True

    def __init__(self, jobs: list[DeviceAiSearchJob | None]) -> None:
        self.jobs = jobs

    async def claim_device_job(self, model_key: str) -> DeviceAiSearchJob | None:
        assert model_key == "hybrid-solider-clip-v1"
        return self.jobs.pop(0)


class _CurrentDeviceWorker:
    model_key = "hybrid-solider-clip-v1"

    def __init__(self) -> None:
        self.claims: list[DeviceAiSearchJob] = []
        self.settings = type("Settings", (), {"model_key": self.model_key})()

    async def process_device_claim(
        self,
        client: _CurrentDeviceClient,
        job: DeviceAiSearchJob,
    ) -> bool:
        self.claims.append(job)
        return True


def test_current_device_rabbit_event_is_only_a_wakeup_signal() -> None:
    event = RabbitWorkerJobEvent.model_validate(
        {
            "commandId": "command-71",
            "eventType": "RECORDING_ANALYSIS_JOB_CREATED",
            "jobId": 71,
            "occurredAt": "2026-07-30T00:00:00Z",
        }
    )
    delivery = _Delivery(event.model_dump_json(by_alias=True).encode())
    worker = _CurrentDeviceWorker()
    processor = RabbitJobProcessor(
        worker,  # type: ignore[arg-type]
        retry_scheduler=_RetryScheduler(),
        retry_delay_seconds=5.0,
        max_retry_attempts=3,
    )

    async def scenario() -> bool:
        return await processor.handle(
            delivery,
            _CurrentDeviceClient([_job(71), None]),
        )  # type: ignore[arg-type]

    assert anyio.run(scenario) is True
    assert delivery.acked == 1
    assert delivery.rejected == []
    assert [job.job_id for job in worker.claims] == [71]


def test_current_device_event_drains_older_queued_jobs_before_waiting() -> None:
    event = RabbitWorkerJobEvent.model_validate(
        {
            "commandId": "command-71",
            "eventType": "RECORDING_ANALYSIS_JOB_CREATED",
            "jobId": 71,
            "occurredAt": "2026-07-30T00:00:00Z",
        }
    )
    delivery = _Delivery(event.model_dump_json(by_alias=True).encode())
    worker = _CurrentDeviceWorker()
    processor = RabbitJobProcessor(
        worker,  # type: ignore[arg-type]
        retry_scheduler=_RetryScheduler(),
        retry_delay_seconds=5.0,
        max_retry_attempts=3,
    )

    async def scenario() -> bool:
        return await processor.handle(
            delivery,
            _CurrentDeviceClient([_job(71), _job(72), None]),
        )  # type: ignore[arg-type]

    assert anyio.run(scenario) is True
    assert delivery.acked == 1
    assert delivery.rejected == []
    assert [job.job_id for job in worker.claims] == [71, 72]
