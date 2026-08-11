from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Decision = Literal["match", "review", "reject"]


class SearchCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    color: str | None = Field(default=None, max_length=40)
    clothing: str | None = Field(default=None, max_length=80)
    object_name: str | None = Field(default=None, max_length=80)


class CandidateAnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(min_length=1, max_length=80)
    camera_id: str = Field(min_length=1, max_length=80)
    track_id: str = Field(min_length=1, max_length=80)
    image_path: str = Field(min_length=1, max_length=500)
    search_condition: SearchCondition = Field(default_factory=SearchCondition)

    @field_validator("image_path")
    @classmethod
    def reject_remote_image(cls, value: str) -> str:
        if "://" in value or value.startswith(("data:", "ftp:")):
            raise ValueError("image_path must be a server-local file path")
        return value


class CandidateAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    color: str | None = Field(default=None, max_length=40)
    clothing: str | None = Field(default=None, max_length=80)
    object_name: str | None = Field(default=None, max_length=80)


class CandidateAnalysisResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    camera_id: str
    track_id: str
    decision: Decision
    attributes: CandidateAttributes
    confidence: float = Field(ge=0.0, le=1.0)
    model_version: str = Field(alias="modelVersion", min_length=1)
    latency_ms: float = Field(alias="latencyMs", ge=0.0)
    failure_reason: str | None = Field(default=None, alias="failureReason")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class HealthResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal["ok", "degraded"]
    provider: str
    model_loaded: bool = Field(alias="modelLoaded")
    model_version: str = Field(alias="modelVersion")

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class ErrorResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    code: str
    message: str


class TeacherLabel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: str = Field(alias="schemaVersion", min_length=1)
    sample_id: str = Field(alias="sampleId", min_length=1)
    case_id: str = Field(alias="caseId", min_length=1)
    image_path: str = Field(alias="imagePath", min_length=1)
    attributes: CandidateAttributes
    candidate_quality: Literal["keep", "review", "discard"] = Field(alias="candidateQuality")
    reason: str = Field(min_length=1, max_length=500)
    teacher_model: str = Field(alias="teacherModel", min_length=1)
    teacher_version: str = Field(alias="teacherVersion", min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


def validate_local_image(path_value: str) -> Path:
    path = Path(path_value).expanduser()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("image_path must point to jpg, jpeg, png, or webp")
    return path
