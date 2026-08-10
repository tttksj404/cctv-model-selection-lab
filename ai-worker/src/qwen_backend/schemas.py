from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Decision = Literal["match", "review", "reject"]


class SearchCondition(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    color: str | None = Field(default=None, max_length=40)
    clothing: str | None = Field(default=None, max_length=80)
    object_name: str | None = Field(default=None, alias="objectName", max_length=80)
    texture: tuple[str, ...] = Field(default=(), max_length=8)


class CandidateAnalysisRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    case_id: str = Field(alias="caseId", min_length=1, max_length=80)
    camera_id: str = Field(alias="cameraId", min_length=1, max_length=80)
    track_id: str = Field(alias="trackId", min_length=1, max_length=80)
    image_path: str = Field(alias="imagePath", min_length=1, max_length=500)
    search_condition: SearchCondition = Field(
        default_factory=SearchCondition, alias="searchCondition"
    )

    @field_validator("image_path")
    @classmethod
    def reject_remote_image(cls, value: str) -> str:
        if "://" in value or value.startswith(("data:", "ftp:")):
            raise ValueError("image_path must be a server-local file path")
        return value


class CandidateAttributes(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)

    color: str | None = Field(default=None, max_length=40)
    clothing: str | None = Field(default=None, max_length=80)
    object_name: str | None = Field(default=None, alias="objectName", max_length=80)
    texture: tuple[str, ...] = Field(default=(), max_length=8)


class CandidateAnalysisResponse(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    camera_id: str
    track_id: str
    decision: Decision
    attributes: CandidateAttributes
    confidence: float = Field(ge=0.0, le=1.0)
    semantic_match_score: float | None = Field(
        default=None, alias="semanticMatchScore", ge=0.0, le=1.0
    )
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
    server_attribute_enabled: bool = Field(alias="serverAttributeEnabled")
    server_attribute_ready: bool = Field(alias="serverAttributeReady")
    server_attribute_model: str | None = Field(default=None, alias="serverAttributeModel")
    server_attribute_reasons: tuple[str, ...] = Field(alias="serverAttributeReasons")

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
    prompt_version: str = Field(alias="promptVersion", min_length=1)
    source_hash: str = Field(alias="sourceHash", min_length=1)

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


def validate_local_image(path_value: str, image_root: Path) -> Path:
    root = image_root.expanduser().resolve(strict=True)
    path = Path(path_value).expanduser()
    candidate = (root / path) if not path.is_absolute() else path
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root)
    except (FileNotFoundError, RuntimeError) as exc:
        raise FileNotFoundError(candidate) from exc
    except ValueError as exc:
        raise ValueError("image_path must stay inside the configured image root") from exc
    if not resolved.is_file():
        raise FileNotFoundError(resolved)
    if resolved.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp"}:
        raise ValueError("image_path must point to jpg, jpeg, png, or webp")
    return resolved

