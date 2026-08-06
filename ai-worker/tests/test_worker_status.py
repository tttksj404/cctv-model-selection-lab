from __future__ import annotations

from qwen_backend.worker_status import WorkerStage, WorkerStatusController, WorkerStatusWire


def test_status_controller_keeps_the_latest_inference_snapshot() -> None:
    controller = WorkerStatusController(show_window=False)

    controller.update(
        WorkerStage.INFERENCING,
        "로컬 모델 추론 진행 중",
        job_id=71,
        progress=60,
    )

    snapshot = controller.latest
    assert snapshot.stage is WorkerStage.INFERENCING
    assert snapshot.message == "로컬 모델 추론 진행 중"
    assert snapshot.job_id == 71
    assert snapshot.progress == 60


def test_status_controller_reports_completion_and_candidate_count() -> None:
    controller = WorkerStatusController(show_window=False)

    controller.update(
        WorkerStage.SUCCEEDED,
        "추론 완료",
        job_id=71,
        progress=100,
        candidate_count=2,
    )

    assert controller.latest.stage is WorkerStage.SUCCEEDED
    assert controller.latest.candidate_count == 2
    assert controller.latest.progress == 100


def test_status_wire_round_trip_preserves_stage_and_job() -> None:
    controller = WorkerStatusController(show_window=False)
    controller.update(WorkerStage.INFERENCING, "추론 진행 중", job_id=72, progress=65)

    wire = WorkerStatusWire.from_snapshot(controller.latest)
    restored = WorkerStatusWire.model_validate_json(wire.model_dump_json())

    assert restored.kind == "status"
    assert restored.stage is WorkerStage.INFERENCING
    assert restored.job_id == 72
    assert restored.progress == 65
