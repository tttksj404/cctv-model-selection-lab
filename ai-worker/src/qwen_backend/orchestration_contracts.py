from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

ORCHESTRATION_SCHEMA_VERSION = "eyesonu-orchestration-v1"


class StrictModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
        str_strip_whitespace=True,
    )


class AgentModel(StrEnum):
    YOLO = "yolo"
    CLIP = "clip"
    SOLIDER = "solider"
    PAR = "par"
    QWEN = "qwen"
    GROUNDING_DINO = "grounding_dino"
    SAM2 = "sam2"
    SONNET = "sonnet"


class HarnessStatus(StrEnum):
    READY = "ready"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"


class NodeStatus(StrEnum):
    SUCCEEDED = "succeeded"
    UNAVAILABLE = "unavailable"
    FAILED = "failed"
    BLOCKED = "blocked"


class HarnessRequest(StrictModel):
    schema_version: Literal["eyesonu-orchestration-v1"] = ORCHESTRATION_SCHEMA_VERSION
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    track_id: str = Field(min_length=1, max_length=200)
    image_ref: str = Field(min_length=1, max_length=2_000)
    prompt: str = Field(min_length=1, max_length=2_000)
    exclusion_prompt: str | None = Field(default=None, max_length=2_000)


class ModelObservation(StrictModel):
    model: AgentModel
    status: HarnessStatus
    score: float | None = Field(default=None, ge=0.0, le=1.0)
    latency_ms: float = Field(default=0.0, ge=0.0)
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    output_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reason: str | None = Field(default=None, max_length=1_000)


class GraphNodeResult(StrictModel):
    node_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,63}$")
    model: AgentModel | None
    status: NodeStatus
    elapsed_ms: float = Field(ge=0.0)
    observation: ModelObservation | None = None
    reason: str | None = Field(default=None, max_length=1_000)


class GraphRun(StrictModel):
    schema_version: Literal["eyesonu-orchestration-v1"] = ORCHESTRATION_SCHEMA_VERSION
    job_id: int = Field(gt=0)
    track_id: str = Field(min_length=1, max_length=200)
    final_status: NodeStatus
    trace: tuple[GraphNodeResult, ...]
