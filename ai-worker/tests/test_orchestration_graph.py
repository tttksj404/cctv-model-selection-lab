from __future__ import annotations

import pytest

from qwen_backend.model_harness import ModelHarness
from qwen_backend.orchestration_contracts import (
    AgentModel,
    HarnessRequest,
    HarnessStatus,
    ModelObservation,
    NodeStatus,
)
from qwen_backend.orchestration_graph import GraphNodeSpec, OrchestrationGraph, build_default_graph


class FixtureAgent:
    def __init__(self, model: AgentModel) -> None:
        self.model = model

    def infer(self, request: HarnessRequest) -> ModelObservation:
        del request
        return ModelObservation(
            model=self.model,
            status=HarnessStatus.READY,
            score=0.8,
            input_sha256="0" * 64,
        )


def _request() -> HarnessRequest:
    return HarnessRequest(
        job_id=10,
        case_id=20,
        track_id="track-10",
        image_ref="crop.jpg",
        prompt="black pants",
    )


def test_default_graph_runs_core_models_and_keeps_qwen_optional() -> None:
    agents = {
        model: FixtureAgent(model)
        for model in (AgentModel.YOLO, AgentModel.CLIP, AgentModel.SOLIDER, AgentModel.PAR)
    }

    result = build_default_graph().run(_request(), ModelHarness(agents))

    assert result.final_status is NodeStatus.SUCCEEDED
    assert [item.node_id for item in result.trace][-1] == "late_fusion_decision"
    qwen = next(item for item in result.trace if item.node_id == "qwen_review")
    assert qwen.status is NodeStatus.UNAVAILABLE


def test_default_graph_blocks_when_required_reid_is_unavailable() -> None:
    agents = {
        model: FixtureAgent(model) for model in (AgentModel.YOLO, AgentModel.CLIP, AgentModel.PAR)
    }

    result = build_default_graph().run(_request(), ModelHarness(agents))

    assert result.final_status is NodeStatus.BLOCKED
    evidence = next(item for item in result.trace if item.node_id == "evidence_contract")
    assert evidence.status is NodeStatus.BLOCKED


def test_graph_rejects_cycles() -> None:
    with pytest.raises(ValueError, match="cycle"):
        OrchestrationGraph(
            (
                GraphNodeSpec(node_id="node_a", dependencies=("node_b",)),
                GraphNodeSpec(node_id="node_b", dependencies=("node_a",)),
            )
        )
