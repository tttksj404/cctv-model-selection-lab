from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Protocol, runtime_checkable

from qwen_backend.orchestration_contracts import (
    AgentModel,
    HarnessRequest,
    HarnessStatus,
    ModelObservation,
)


class ModelAgentError(RuntimeError):
    """A model agent could not produce a trustworthy observation."""


@runtime_checkable
class ModelAgent(Protocol):
    model: AgentModel

    def infer(self, request: HarnessRequest) -> ModelObservation: ...


def request_fingerprint(request: HarnessRequest) -> str:
    payload = request.model_dump_json().encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class ModelHarness:
    """Uniform boundary for model agents used by the graph.

    The harness records availability, latency, and fingerprints.  It never
    converts a missing or failed model into a positive score.
    """

    def __init__(self, agents: Mapping[AgentModel, ModelAgent]) -> None:
        self._agents = agents

    def run(self, model: AgentModel, request: HarnessRequest) -> ModelObservation:
        input_sha256 = request_fingerprint(request)
        agent = self._agents.get(model)
        if agent is None:
            return ModelObservation(
                model=model,
                status=HarnessStatus.UNAVAILABLE,
                input_sha256=input_sha256,
                reason="model agent is not configured",
            )

        started = perf_counter()
        try:
            observation = agent.infer(request)
        except (ModelAgentError, OSError, RuntimeError, ValueError) as exc:
            return ModelObservation(
                model=model,
                status=HarnessStatus.FAILED,
                latency_ms=(perf_counter() - started) * 1_000.0,
                input_sha256=input_sha256,
                reason=f"{type(exc).__name__}: {exc}",
            )

        if observation.model is not model:
            raise ModelAgentError(
                f"agent identity mismatch: expected {model.value}, got {observation.model.value}"
            )
        return observation.model_copy(
            update={
                "latency_ms": (perf_counter() - started) * 1_000.0,
                "input_sha256": input_sha256,
            }
        )

    def run_many(
        self, models: Sequence[AgentModel], request: HarnessRequest
    ) -> tuple[ModelObservation, ...]:
        return tuple(self.run(model, request) for model in models)
