from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import TYPE_CHECKING

from qwen_backend.worker_status import (
    STAGE_LABELS,
    WorkerStage,
    WorkerStatusSnapshot,
    WorkerStatusWire,
)

if TYPE_CHECKING:
    import tkinter as tk
    from tkinter import ttk

logger = logging.getLogger(__name__)

WINDOW_BACKGROUND = "#F7F9FC"
PANEL_BACKGROUND = "#FFFFFF"
TEXT_PRIMARY = "#273247"
TEXT_MUTED = "#6F7785"
BORDER = "#DDE4ED"
ACCENT = "#1F8EA6"
SUCCESS = "#2D9465"
WARNING = "#D59627"
ERROR = "#C24C3D"


@dataclass(frozen=True, slots=True)
class _UiRefs:
    badge: tk.Label
    message: tk.Label
    progress: ttk.Progressbar
    job: tk.Label
    candidates: tk.Label
    updated: tk.Label
    log: tk.Text


class WorkerStatusWindow:
    """Run the Tk UI in a child process so it cannot disturb async inference."""

    def __init__(self) -> None:
        self._queue: Queue[WorkerStatusWire] = Queue(maxsize=1)
        self._closed = Event()
        self._process: subprocess.Popen[str] | None = None
        self._sender: Thread | None = None

    def start(self) -> None:
        if self._process is not None:
            return
        self._process = subprocess.Popen(
            [sys.executable, "-m", "qwen_backend.worker_status_process"],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            creationflags=0x08000000 if sys.platform == "win32" else 0,
        )
        self._sender = Thread(
            target=self._send_messages,
            name="eyesonu-worker-status-sender",
            daemon=True,
        )
        self._sender.start()

    def publish(self, snapshot: WorkerStatusSnapshot) -> None:
        if self._closed.is_set():
            return
        self._replace_latest(WorkerStatusWire.from_snapshot(snapshot))

    def close(self) -> None:
        self._closed.set()
        self._replace_latest(WorkerStatusWire(kind="close"))
        sender = self._sender
        if sender is not None:
            sender.join(timeout=2.0)
        process = self._process
        if process is not None:
            try:
                process.wait(timeout=2.0)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=2.0)
        self._sender = None
        self._process = None

    def _replace_latest(self, item: WorkerStatusWire) -> None:
        try:
            self._queue.get_nowait()
        except Empty:
            pass
        try:
            self._queue.put_nowait(item)
        except Full:
            return

    def _send_messages(self) -> None:
        while True:
            item = self._queue.get()
            process = self._process
            if process is None or process.stdin is None:
                return
            try:
                process.stdin.write(item.model_dump_json() + "\n")
                process.stdin.flush()
            except (BrokenPipeError, OSError, ValueError) as exception:
                logger.warning("AI Worker status process stopped: %s", exception)
                return
            if item.kind == "close":
                return


def build_status_widgets(root: tk.Tk) -> _UiRefs:
    import tkinter as tk
    from tkinter import ttk

    style = ttk.Style(root)
    style.configure("Worker.Horizontal.TProgressbar", troughcolor=BORDER, background=ACCENT)
    root.columnconfigure(0, weight=1)
    root.rowconfigure(1, weight=1)

    header = tk.Frame(root, background=WINDOW_BACKGROUND, padx=28, pady=22)
    header.grid(row=0, column=0, sticky="ew")
    tk.Label(
        header,
        text="EYES:ON U",
        font=("Segoe UI", 10, "bold"),
        foreground=ACCENT,
        background=WINDOW_BACKGROUND,
    ).pack(anchor="w")
    tk.Label(
        header,
        text="AI Worker 실시간 추론 상태",
        font=("Segoe UI", 21, "bold"),
        foreground=TEXT_PRIMARY,
        background=WINDOW_BACKGROUND,
    ).pack(anchor="w", pady=(5, 0))

    body = tk.Frame(root, background=WINDOW_BACKGROUND, padx=28, pady=0)
    body.grid(row=1, column=0, sticky="nsew", pady=22)
    body.columnconfigure(0, weight=1)
    body.rowconfigure(3, weight=1)

    status_card = tk.Frame(
        body,
        background=PANEL_BACKGROUND,
        highlightbackground=BORDER,
        highlightthickness=1,
        padx=20,
        pady=18,
    )
    status_card.grid(row=0, column=0, sticky="ew")
    status_card.columnconfigure(0, weight=1)
    badge = tk.Label(
        status_card,
        text="대기",
        font=("Segoe UI", 10, "bold"),
        padx=10,
        pady=5,
        foreground=TEXT_PRIMARY,
        background=BORDER,
    )
    badge.grid(row=0, column=0, sticky="w")
    message = tk.Label(
        status_card,
        text="백엔드 작업 대기 중",
        font=("Segoe UI", 15, "bold"),
        foreground=TEXT_PRIMARY,
        background=PANEL_BACKGROUND,
    )
    message.grid(row=1, column=0, sticky="w", pady=(14, 8))
    progress = ttk.Progressbar(
        status_card,
        mode="determinate",
        maximum=100,
        style="Worker.Horizontal.TProgressbar",
    )
    progress.grid(row=2, column=0, sticky="ew")

    details = tk.Frame(body, background=WINDOW_BACKGROUND, pady=14)
    details.grid(row=1, column=0, sticky="ew")
    details.columnconfigure(0, weight=1)
    details.columnconfigure(1, weight=1)
    details.columnconfigure(2, weight=1)
    detail_labels = tuple(
        tk.Label(
            details,
            text=value,
            font=("Segoe UI", 10),
            foreground=TEXT_MUTED,
            background=WINDOW_BACKGROUND,
        )
        for value in ("작업 ID  대기 중", "후보  -", "최근 업데이트  -")
    )
    for column, label in enumerate(detail_labels):
        label.grid(row=0, column=column, sticky="w")

    tk.Label(
        body,
        text="실행 로그",
        font=("Segoe UI", 11, "bold"),
        foreground=TEXT_PRIMARY,
        background=WINDOW_BACKGROUND,
    ).grid(row=2, column=0, sticky="w", pady=7)
    log_frame = tk.Frame(
        body,
        background=PANEL_BACKGROUND,
        highlightbackground=BORDER,
        highlightthickness=1,
    )
    log_frame.grid(row=3, column=0, sticky="nsew")
    log = tk.Text(
        log_frame,
        height=8,
        wrap="word",
        state="disabled",
        font=("Consolas", 9),
        foreground=TEXT_MUTED,
        background=PANEL_BACKGROUND,
        borderwidth=0,
        padx=12,
        pady=10,
    )
    log.pack(fill="both", expand=True)
    return _UiRefs(
        badge,
        message,
        progress,
        detail_labels[0],
        detail_labels[1],
        detail_labels[2],
        log,
    )


def render_status_snapshot(snapshot: WorkerStatusSnapshot, refs: _UiRefs) -> None:
    color = _stage_color(snapshot.stage)
    refs.badge.configure(
        text=STAGE_LABELS[snapshot.stage],
        foreground="#FFFFFF",
        background=color,
    )
    refs.message.configure(text=snapshot.message)
    refs.progress.configure(value=snapshot.progress)
    job_text = "대기 중" if snapshot.job_id is None else str(snapshot.job_id)
    candidate_text = "-" if snapshot.candidate_count is None else str(snapshot.candidate_count)
    refs.job.configure(text=f"작업 ID  {job_text}")
    refs.candidates.configure(text=f"후보  {candidate_text}")
    refs.updated.configure(text=f"최근 업데이트  {_format_time(snapshot.occurred_at)}")
    refs.log.configure(state="normal")
    refs.log.insert("end", f"[{_format_time(snapshot.occurred_at)}] {snapshot.message}\n")
    refs.log.see("end")
    refs.log.configure(state="disabled")


def _format_time(value: datetime) -> str:
    return value.astimezone().strftime("%H:%M:%S")


def _stage_color(stage: WorkerStage) -> str:
    if stage is WorkerStage.SUCCEEDED:
        return SUCCESS
    if stage is WorkerStage.FAILED:
        return ERROR
    if stage in {WorkerStage.RECONNECTING, WorkerStage.WAITING}:
        return WARNING
    return ACCENT
