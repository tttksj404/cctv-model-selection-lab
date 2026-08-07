from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from threading import Lock
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, Protocol

from pydantic import BaseModel

if TYPE_CHECKING:
    from qwen_backend.worker_status_window import WorkerStatusWindow

logger = logging.getLogger(__name__)


class WorkerStage(StrEnum):
    WAITING = "waiting"
    WARMING = "warming"
    RECEIVED = "received"
    CLAIMING = "claiming"
    FETCHING_TARGET = "fetching_target"
    DOWNLOADING = "downloading"
    INFERENCING = "inferencing"
    UPLOADING = "uploading"
    COMPLETING = "completing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    RECONNECTING = "reconnecting"


STAGE_LABELS: Mapping[WorkerStage, str] = MappingProxyType(
    {
        WorkerStage.WARMING: "모델 준비 중",
        WorkerStage.WAITING: "백엔드 작업 대기 중",
        WorkerStage.RECEIVED: "작업 수신",
        WorkerStage.CLAIMING: "작업 점유 확인",
        WorkerStage.FETCHING_TARGET: "작업 정보 확인",
        WorkerStage.DOWNLOADING: "녹화본 다운로드",
        WorkerStage.INFERENCING: "추론 진행 중",
        WorkerStage.UPLOADING: "후보 증거 업로드",
        WorkerStage.COMPLETING: "결과 저장 중",
        WorkerStage.SUCCEEDED: "추론 완료",
        WorkerStage.FAILED: "추론 실패",
        WorkerStage.RECONNECTING: "연결 재시도 중",
    }
)

STAGE_PROGRESS: Mapping[WorkerStage, int] = MappingProxyType(
    {
        WorkerStage.WARMING: 0,
        WorkerStage.WAITING: 0,
        WorkerStage.RECEIVED: 3,
        WorkerStage.CLAIMING: 8,
        WorkerStage.FETCHING_TARGET: 15,
        WorkerStage.DOWNLOADING: 30,
        WorkerStage.INFERENCING: 65,
        WorkerStage.UPLOADING: 85,
        WorkerStage.COMPLETING: 95,
        WorkerStage.SUCCEEDED: 100,
        WorkerStage.FAILED: 100,
        WorkerStage.RECONNECTING: 0,
    }
)


@dataclass(frozen=True, slots=True)
class WorkerStatusSnapshot:
    stage: WorkerStage
    message: str
    job_id: int | None
    progress: int
    candidate_count: int | None
    occurred_at: datetime


class WorkerStatusWire(BaseModel):
    """UTF-8 line protocol between the worker and the local status process."""

    kind: Literal["status", "close"]
    stage: WorkerStage | None = None
    message: str | None = None
    job_id: int | None = None
    progress: int = 0
    candidate_count: int | None = None
    occurred_at: datetime | None = None

    @classmethod
    def from_snapshot(cls, snapshot: WorkerStatusSnapshot) -> WorkerStatusWire:
        return cls(
            kind="status",
            stage=snapshot.stage,
            message=snapshot.message,
            job_id=snapshot.job_id,
            progress=snapshot.progress,
            candidate_count=snapshot.candidate_count,
            occurred_at=snapshot.occurred_at,
        )


class WorkerStatusSink(Protocol):
    def update(
        self,
        stage: WorkerStage,
        message: str,
        *,
        job_id: int | None = None,
        progress: int | None = None,
        candidate_count: int | None = None,
    ) -> None: ...


class NullWorkerStatus:
    """No-op sink for direct library use and tests without a desktop window."""

    def update(
        self,
        stage: WorkerStage,
        message: str,
        *,
        job_id: int | None = None,
        progress: int | None = None,
        candidate_count: int | None = None,
    ) -> None:
        return None


class WorkerStatusController:
    """Keep the latest worker state and optionally publish it to a local window."""

    def __init__(self, *, show_window: bool = False) -> None:
        self._show_window = show_window
        self._lock = Lock()
        self._latest = WorkerStatusSnapshot(
            stage=WorkerStage.WAITING,
            message=STAGE_LABELS[WorkerStage.WAITING],
            job_id=None,
            progress=STAGE_PROGRESS[WorkerStage.WAITING],
            candidate_count=None,
            occurred_at=datetime.now(UTC),
        )
        self._window: WorkerStatusWindow | None = None

    @property
    def latest(self) -> WorkerStatusSnapshot:
        with self._lock:
            return self._latest

    def start(self) -> None:
        if not self._show_window or self._window is not None:
            return
        try:
            from qwen_backend.worker_status_window import WorkerStatusWindow

            window = WorkerStatusWindow()
            window.start()
            self._window = window
            window.publish(self.latest)
        except (ImportError, OSError, RuntimeError, ValueError) as exception:
            logger.warning("status window unavailable; worker continues headless: %s", exception)

    def update(
        self,
        stage: WorkerStage,
        message: str,
        *,
        job_id: int | None = None,
        progress: int | None = None,
        candidate_count: int | None = None,
    ) -> None:
        snapshot = WorkerStatusSnapshot(
            stage=stage,
            message=message,
            job_id=job_id,
            progress=_bounded_progress(STAGE_PROGRESS[stage] if progress is None else progress),
            candidate_count=candidate_count,
            occurred_at=datetime.now(UTC),
        )
        with self._lock:
            self._latest = snapshot
            window = self._window
        if window is not None:
            window.publish(snapshot)

    def close(self) -> None:
        window = self._window
        self._window = None
        if window is not None:
            window.close()


def _bounded_progress(progress: int) -> int:
    return max(0, min(100, progress))
