from __future__ import annotations

import sys
import tkinter as tk
from queue import Empty, Queue
from threading import Thread

from pydantic import ValidationError

from qwen_backend.worker_status import WorkerStatusSnapshot, WorkerStatusWire
from qwen_backend.worker_status_window import build_status_widgets, render_status_snapshot


def _read_messages(messages: Queue[WorkerStatusWire]) -> None:
    for raw_line in sys.stdin.buffer:
        try:
            messages.put(WorkerStatusWire.model_validate_json(raw_line))
        except ValidationError:
            continue
    messages.put(WorkerStatusWire(kind="close"))


def _snapshot_from_wire(message: WorkerStatusWire) -> WorkerStatusSnapshot | None:
    if (
        message.kind != "status"
        or message.stage is None
        or message.message is None
        or message.occurred_at is None
    ):
        return None
    return WorkerStatusSnapshot(
        stage=message.stage,
        message=message.message,
        job_id=message.job_id,
        progress=message.progress,
        candidate_count=message.candidate_count,
        occurred_at=message.occurred_at,
    )


def main() -> int:
    root = tk.Tk()
    root.title("EyesOnU · AI Worker")
    root.geometry("760x520")
    root.minsize(640, 420)
    root.configure(background="#F7F9FC")
    refs = build_status_widgets(root)
    messages: Queue[WorkerStatusWire] = Queue()
    Thread(target=_read_messages, args=(messages,), daemon=True).start()

    def poll() -> None:
        should_close = False
        try:
            while True:
                message = messages.get_nowait()
                if message.kind == "close":
                    should_close = True
                    break
                snapshot = _snapshot_from_wire(message)
                if snapshot is not None:
                    render_status_snapshot(snapshot, refs)
        except Empty:
            pass
        if should_close:
            root.destroy()
            return
        root.after(120, poll)

    root.protocol("WM_DELETE_WINDOW", root.destroy)
    root.after(0, poll)
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

