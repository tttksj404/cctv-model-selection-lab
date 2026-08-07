from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import anyio
import pytest

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
)
from qwen_backend.notebook_worker import NotebookWorker
from qwen_backend.worker_settings import NotebookWorkerSettings


class WarmupFixtureEngine:
    model_key = "fixture-lifecycle-v1"

    def __init__(self, events: list[str] | None = None, *, fail_warmup: bool = False) -> None:
        self.events = events if events is not None else []
        self.fail_warmup = fail_warmup
        self.warmup_calls = 0
        self.analyze_calls = 0

    def warm_up(self) -> None:
        self.warmup_calls += 1
        self.events.append("warmup")
        if self.fail_warmup:
            raise RuntimeError("fixture model warm-up failed")

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        self.analyze_calls += 1
        self.events.append("analyze")
        return CandidateRuntimeResponse(modelKey=self.model_key, candidates=())


def _settings(tmp_path: Path) -> NotebookWorkerSettings:
    return NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="worker-key",
        worker_id="lifecycle-test",
        model_key=WarmupFixtureEngine.model_key,
        cache_dir=tmp_path / "cache",
        output_dir=tmp_path / "output",
    )


def _request(tmp_path: Path) -> CandidateRuntimeRequest:
    video_path = tmp_path / "recording.mp4"
    video_path.write_bytes(b"video")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    return CandidateRuntimeRequest(
        modelKey=WarmupFixtureEngine.model_key,
        jobId=1,
        caseId=2,
        recordingId=3,
        cameraId=4,
        cameraName="fixture",
        cameraAddress="fixture://camera",
        videoPath=video_path,
        referencePath=None,
        outputDir=output_dir,
        prompt="red jacket",
        exclusionPrompt=None,
    )


def test_worker_reuses_one_warmed_engine_for_repeated_runtime_calls(tmp_path: Path) -> None:
    engine = WarmupFixtureEngine()
    factory_calls = 0

    def factory() -> WarmupFixtureEngine:
        nonlocal factory_calls
        factory_calls += 1
        return engine

    worker = NotebookWorker(_settings(tmp_path), engine_factory=factory)
    request = _request(tmp_path)

    worker._run_local_runtime(request)  # pyright: ignore[reportPrivateUsage]
    worker._run_local_runtime(request)  # pyright: ignore[reportPrivateUsage]

    assert factory_calls == 1
    assert engine.warmup_calls == 1
    assert engine.analyze_calls == 2


def test_worker_serializes_engine_initialization_across_runtime_threads(tmp_path: Path) -> None:
    engine = WarmupFixtureEngine()
    factory_started = Event()
    release_factory = Event()
    factory_calls = 0

    def factory() -> WarmupFixtureEngine:
        nonlocal factory_calls
        factory_calls += 1
        factory_started.set()
        assert release_factory.wait(timeout=2.0)
        return engine

    worker = NotebookWorker(_settings(tmp_path), engine_factory=factory)
    request = _request(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(worker._run_local_runtime, request)  # pyright: ignore[reportPrivateUsage]
        assert factory_started.wait(timeout=2.0)
        second = executor.submit(worker._run_local_runtime, request)  # pyright: ignore[reportPrivateUsage]
        release_factory.set()
        first.result(timeout=3.0)
        second.result(timeout=3.0)

    assert factory_calls == 1
    assert engine.warmup_calls == 1


def test_worker_does_not_consume_queue_before_model_warmup(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    engine = WarmupFixtureEngine(events)

    class FakeRabbitWorker:
        def __init__(self, worker: NotebookWorker) -> None:
            events.append("consumer_created")

        async def run_once(self) -> bool:
            events.append("consume")
            return False

    monkeypatch.setattr("qwen_backend.rabbit_consumer.RabbitRecordingWorker", FakeRabbitWorker)
    worker = NotebookWorker(_settings(tmp_path), engine_factory=lambda: engine)

    assert anyio.run(worker.run_once) is False
    assert events == ["warmup", "consumer_created", "consume"]


def test_failed_model_warmup_is_not_retried_in_the_same_process(tmp_path: Path) -> None:
    engine = WarmupFixtureEngine(fail_warmup=True)
    factory_calls = 0

    def factory() -> WarmupFixtureEngine:
        nonlocal factory_calls
        factory_calls += 1
        return engine

    worker = NotebookWorker(_settings(tmp_path), engine_factory=factory)

    with pytest.raises(RuntimeError, match="model warm-up failed"):
        worker._ensure_engine_ready()  # pyright: ignore[reportPrivateUsage]
    with pytest.raises(RuntimeError, match="model warm-up failed"):
        worker._ensure_engine_ready()  # pyright: ignore[reportPrivateUsage]

    assert factory_calls == 1
    assert engine.warmup_calls == 1
