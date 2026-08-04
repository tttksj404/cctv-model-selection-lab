from __future__ import annotations

from pathlib import Path
from typing import ClassVar, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

RUNTIME_SCHEMA_VERSION = "eyesonu-candidate-runtime-v1"


class RuntimeModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class RuntimeBoundingBox(RuntimeModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class CandidateRuntimeRequest(RuntimeModel):
    schema_version: Literal["eyesonu-candidate-runtime-v1"] = RUNTIME_SCHEMA_VERSION
    model_key: str = Field(min_length=1, max_length=100)
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    search_condition_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)
    camera_name: str
    camera_address: str
    video_path: Path
    reference_path: Path | None
    output_dir: Path
    prompt: str
    exclusion_prompt: str | None
    similarity_threshold: float = Field(ge=0.0, le=1.0)
    search_from_ms: int = Field(default=0, ge=0)
    search_to_ms: int | None = Field(default=None, gt=0)

    @field_validator("video_path", "reference_path", "output_dir", mode="before")
    @classmethod
    def reject_remote_paths(cls, value: object) -> object:
        if isinstance(value, str) and "://" in value:
            raise ValueError("runtime paths must be server-local")
        return value

    @model_validator(mode="after")
    def validate_search_window(self) -> CandidateRuntimeRequest:
        if self.search_to_ms is not None and self.search_from_ms >= self.search_to_ms:
            raise ValueError("searchFromMs must be earlier than searchToMs")
        return self


class RuntimeCandidate(RuntimeModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame_offset_ms: int = Field(ge=0)
    similarity: float = Field(ge=0.0, le=1.0)
    frame_path: Path
    crop_path: Path
    bounding_box: RuntimeBoundingBox
    attribute_summary: str | None = Field(default=None, max_length=2_000)


class CandidateRuntimeResponse(RuntimeModel):
    schema_version: Literal["eyesonu-candidate-runtime-v1"] = RUNTIME_SCHEMA_VERSION
    model_key: str = Field(min_length=1, max_length=100)
    candidates: tuple[RuntimeCandidate, ...] = Field(max_length=100)


class CandidateRuntimeEngine(Protocol):
    model_key: str

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse: ...


def run_runtime(raw_request: str, engine: CandidateRuntimeEngine) -> str:
    request = CandidateRuntimeRequest.model_validate_json(raw_request)
    if request.model_key != engine.model_key:
        raise ValueError("runtime model key does not match the requested model key")
    if not request.video_path.is_file():
        raise FileNotFoundError(request.video_path)
    if request.reference_path is not None and not request.reference_path.is_file():
        raise FileNotFoundError(request.reference_path)
    if not request.output_dir.is_dir():
        raise FileNotFoundError(request.output_dir)

    response = engine.analyze(request)
    if response.model_key != request.model_key:
        raise ValueError("engine response model key does not match the requested model key")
    output_root = request.output_dir.resolve()
    for candidate in response.candidates:
        if candidate.frame_offset_ms < request.search_from_ms or (
            request.search_to_ms is not None
            and candidate.frame_offset_ms >= request.search_to_ms
        ):
            raise ValueError("engine returned a candidate outside the requested search window")
        for label, source_path in (("frame", candidate.frame_path), ("crop", candidate.crop_path)):
            resolved_path = source_path.resolve()
            if not resolved_path.is_relative_to(output_root):
                raise ValueError(f"candidate {label} escaped the runtime output directory")
            if not resolved_path.is_file():
                raise FileNotFoundError(resolved_path)
    return response.model_dump_json(by_alias=True)
