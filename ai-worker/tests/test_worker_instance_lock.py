from __future__ import annotations

from multiprocessing import get_context
from multiprocessing.connection import Connection
from pathlib import Path

import anyio
import pytest

from qwen_backend.notebook_worker import NotebookWorker
from qwen_backend.worker_instance_lock import (
    WorkerInstanceAlreadyRunningError,
    WorkerInstanceLock,
)
from qwen_backend.worker_settings import NotebookWorkerSettings


def _hold_lock(lock_path: str, ready: Connection, release: Connection) -> None:
    with WorkerInstanceLock(Path(lock_path)):
        ready.send(True)
        release.recv()


def test_second_process_cannot_acquire_worker_lock(tmp_path: Path) -> None:
    lock_path = tmp_path / "worker.lock"
    context = get_context("spawn")
    ready_parent, ready_child = context.Pipe(False)
    release_child, release_parent = context.Pipe(False)
    process = context.Process(
        target=_hold_lock,
        args=(str(lock_path), ready_child, release_child),
    )

    process.start()
    assert ready_parent.recv() is True
    try:
        with pytest.raises(WorkerInstanceAlreadyRunningError):
            with WorkerInstanceLock(lock_path):
                pass
    finally:
        release_parent.send(True)
        process.join(timeout=5)

    assert process.exitcode == 0


def test_worker_lock_is_released_after_context_exit(tmp_path: Path) -> None:
    lock_path = tmp_path / "worker.lock"

    with WorkerInstanceLock(lock_path):
        pass

    with WorkerInstanceLock(lock_path):
        pass


def test_worker_settings_scope_default_lock_to_worker_cache(tmp_path: Path) -> None:
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="worker-key",
        cache_dir=tmp_path / "cache",
    )

    assert settings.single_instance is True
    assert settings.resolved_instance_lock_file() == tmp_path / "cache" / "worker.lock"


def test_notebook_worker_refuses_to_consume_while_another_instance_holds_lock(
    tmp_path: Path,
) -> None:
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="worker-key",
        cache_dir=tmp_path / "cache",
    )
    worker = NotebookWorker(settings, engine_factory=lambda: pytest.fail("warm-up must not run"))

    with WorkerInstanceLock(settings.resolved_instance_lock_file()):
        with pytest.raises(WorkerInstanceAlreadyRunningError):
            anyio.run(worker.run_once)
