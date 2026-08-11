from __future__ import annotations

from collections.abc import Sequence
from time import perf_counter

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from qwen_backend.model_harness import ModelHarness
from qwen_backend.orchestration_contracts import (
    AgentModel,
    GraphNodeResult,
    GraphRun,
    HarnessRequest,
    HarnessStatus,
    NodeStatus,
)


class GraphNodeSpec(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )

    node_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    model: AgentModel | None = None
    dependencies: tuple[str, ...] = ()
    optional_dependencies: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_optional_dependencies(self) -> GraphNodeSpec:
        unknown = set(self.optional_dependencies) - set(self.dependencies)
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"optional dependencies must be declared dependencies: {names}")
        return self


class OrchestrationGraph:
    def __init__(self, nodes: Sequence[GraphNodeSpec]) -> None:
        if not nodes:
            raise ValueError("orchestration graph requires at least one node")
        by_id: dict[str, GraphNodeSpec] = {}
        for node in nodes:
            if node.node_id in by_id:
                raise ValueError(f"duplicate graph node: {node.node_id}")
            by_id[node.node_id] = node
        for node in nodes:
            missing = set(node.dependencies) - set(by_id)
            if missing:
                names = ", ".join(sorted(missing))
                raise ValueError(f"node {node.node_id} has unknown dependencies: {names}")
        self._nodes = by_id
        self._order = self._topological_order()

    @property
    def node_ids(self) -> tuple[str, ...]:
        return self._order

    def _topological_order(self) -> tuple[str, ...]:
        temporary: set[str] = set()
        permanent: set[str] = set()
        ordered: list[str] = []

        def visit(node_id: str) -> None:
            if node_id in permanent:
                return
            if node_id in temporary:
                raise ValueError(f"orchestration graph contains a cycle at {node_id}")
            temporary.add(node_id)
            for dependency in self._nodes[node_id].dependencies:
                visit(dependency)
            temporary.remove(node_id)
            permanent.add(node_id)
            ordered.append(node_id)

        for node_id in self._nodes:
            visit(node_id)
        return tuple(ordered)

    def run(self, request: HarnessRequest, harness: ModelHarness) -> GraphRun:
        results: dict[str, GraphNodeResult] = {}
        for node_id in self._order:
            spec = self._nodes[node_id]
            blocked = [
                dependency
                for dependency in spec.dependencies
                if dependency not in spec.optional_dependencies
                and results[dependency].status is not NodeStatus.SUCCEEDED
            ]
            if blocked:
                results[node_id] = GraphNodeResult(
                    node_id=node_id,
                    model=spec.model,
                    status=NodeStatus.BLOCKED,
                    elapsed_ms=0.0,
                    reason=f"required dependency unavailable: {', '.join(blocked)}",
                )
                continue

            started = perf_counter()
            if spec.model is None:
                results[node_id] = GraphNodeResult(
                    node_id=node_id,
                    model=None,
                    status=NodeStatus.SUCCEEDED,
                    elapsed_ms=(perf_counter() - started) * 1_000.0,
                )
                continue

            observation = harness.run(spec.model, request)
            status = {
                HarnessStatus.READY: NodeStatus.SUCCEEDED,
                HarnessStatus.UNAVAILABLE: NodeStatus.UNAVAILABLE,
                HarnessStatus.FAILED: NodeStatus.FAILED,
            }[observation.status]
            results[node_id] = GraphNodeResult(
                node_id=node_id,
                model=spec.model,
                status=status,
                elapsed_ms=(perf_counter() - started) * 1_000.0,
                observation=observation,
                reason=observation.reason,
            )

        final = results[self._order[-1]]
        return GraphRun(
            job_id=request.job_id,
            track_id=request.track_id,
            final_status=final.status,
            trace=tuple(results[node_id] for node_id in self._order),
        )


def build_default_graph(include_teacher_shadow: bool = False) -> OrchestrationGraph:
    """Build the production-shaped graph without changing the legacy engine.

    Teacher nodes are shadow branches.  They enrich evidence when configured,
    but they are never silently treated as a positive identity decision.
    """

    nodes: list[GraphNodeSpec] = [
        GraphNodeSpec(node_id="detect_tracks", model=AgentModel.YOLO),
        GraphNodeSpec(
            node_id="quality_gate",
            dependencies=("detect_tracks",),
        ),
        GraphNodeSpec(
            node_id="clip_retrieval",
            model=AgentModel.CLIP,
            dependencies=("quality_gate",),
        ),
        GraphNodeSpec(
            node_id="solider_reid",
            model=AgentModel.SOLIDER,
            dependencies=("quality_gate",),
        ),
        GraphNodeSpec(
            node_id="par_attributes",
            model=AgentModel.PAR,
            dependencies=("quality_gate",),
        ),
    ]
    if include_teacher_shadow:
        nodes.extend(
            (
                GraphNodeSpec(
                    node_id="grounding_dino_shadow",
                    model=AgentModel.GROUNDING_DINO,
                    dependencies=("detect_tracks",),
                    optional_dependencies=("detect_tracks",),
                ),
                GraphNodeSpec(
                    node_id="sam2_shadow",
                    model=AgentModel.SAM2,
                    dependencies=("grounding_dino_shadow",),
                    optional_dependencies=("grounding_dino_shadow",),
                ),
                GraphNodeSpec(
                    node_id="sonnet_shadow",
                    model=AgentModel.SONNET,
                    dependencies=("par_attributes",),
                    optional_dependencies=("par_attributes",),
                ),
            )
        )
    evidence_dependencies = ["clip_retrieval", "solider_reid", "par_attributes"]
    optional_evidence = ["par_attributes"]
    if include_teacher_shadow:
        evidence_dependencies.extend(("grounding_dino_shadow", "sam2_shadow", "sonnet_shadow"))
        optional_evidence.extend(("grounding_dino_shadow", "sam2_shadow", "sonnet_shadow"))
    nodes.extend(
        (
            GraphNodeSpec(
                node_id="evidence_contract",
                dependencies=tuple(evidence_dependencies),
                optional_dependencies=tuple(optional_evidence),
            ),
            GraphNodeSpec(
                node_id="qwen_review",
                model=AgentModel.QWEN,
                dependencies=("evidence_contract",),
                optional_dependencies=("evidence_contract",),
            ),
            GraphNodeSpec(
                node_id="late_fusion_decision",
                dependencies=("evidence_contract", "qwen_review"),
                optional_dependencies=("qwen_review",),
            ),
        )
    )
    return OrchestrationGraph(nodes)
