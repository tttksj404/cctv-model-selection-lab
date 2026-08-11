from __future__ import annotations

from qwen_backend.model_harness import ModelHarness
from qwen_backend.orchestration_contracts import (
    AgentModel,
    HarnessRequest,
    HarnessStatus,
    ModelObservation,
)


class FixtureAgent:
    def __init__(self, model: AgentModel, score: float) -> None:
        self.model = model
        self._score = score

    def infer(self, request: HarnessRequest) -> ModelObservation:
        del request
        return ModelObservation(
            model=self.model,
            status=HarnessStatus.READY,
            score=self._score,
            input_sha256="0" * 64,
        )


def _request() -> HarnessRequest:
    return HarnessRequest(
        job_id=1,
        case_id=2,
        track_id="track-a",
        image_ref="crop-a.jpg",
        prompt="gray shirt and black pants",
    )


def test_harness_records_input_fingerprint_and_latency() -> None:
    harness = ModelHarness({AgentModel.CLIP: FixtureAgent(AgentModel.CLIP, 0.8)})

    observation = harness.run(AgentModel.CLIP, _request())

    assert observation.status is HarnessStatus.READY
    assert observation.score == 0.8
    assert observation.input_sha256 != "0" * 64
    assert len(observation.input_sha256) == 64
    assert observation.latency_ms >= 0.0


def test_harness_does_not_turn_missing_agent_into_positive_evidence() -> None:
    observation = ModelHarness({}).run(AgentModel.SOLIDER, _request())

    assert observation.status is HarnessStatus.UNAVAILABLE
    assert observation.score is None
