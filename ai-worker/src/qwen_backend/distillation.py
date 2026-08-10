from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import CandidateAttributes, Decision, validate_local_image

SourceKind = Literal["human", "open_model", "synthetic_fixture", "florence", "sonnet"]
ApprovalStatus = Literal["pending", "approved", "rejected"]

_ALLOWED_TEACHERS: dict[SourceKind, frozenset[str]] = {
    "human": frozenset(("human-review", "human-reviewed")),
    "open_model": frozenset(
        ("local", "grounding-dino-sam2-local", "clip-grounding-dino-sam2.1-local")
    ),
    "synthetic_fixture": frozenset(("synthetic-fixture",)),
    "florence": frozenset(("microsoft/Florence-2-large",)),
    "sonnet": frozenset(("claude-sonnet-5",)),
}
_ALLOWED_PROMPTS = frozenset(
    ("candidate-v1", "florence-attributes-v1", "manual-v1", "sonnet-candidate-v1", "v1")
)


class DistillationDataError(ValueError):
    pass


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    source_kind: SourceKind = Field(alias="sourceKind")
    teacher_model: str = Field(alias="teacherModel", min_length=1)
    prompt_version: str = Field(alias="promptVersion", min_length=1)
    source_hash: str = Field(alias="sourceHash", pattern=r"^[0-9a-f]{64}$")
    approval_status: ApprovalStatus = Field(default="pending", alias="approvalStatus")
    reviewed_by: str | None = Field(default=None, alias="reviewedBy", min_length=1)
    teacher_agreement: bool = Field(default=False, alias="teacherAgreement")

    @model_validator(mode="after")
    def validate_provenance_policy(self) -> Provenance:
        allowed_teachers = _ALLOWED_TEACHERS[self.source_kind]
        if self.teacher_model not in allowed_teachers:
            raise ValueError(
                f"teacher model is not allowlisted for source kind {self.source_kind}"
            )
        if self.prompt_version not in _ALLOWED_PROMPTS:
            raise ValueError("prompt version is not allowlisted")
        if (
            self.approval_status == "approved"
            and self.reviewed_by is None
            and not self.teacher_agreement
        ):
            raise ValueError("approved provenance requires reviewedBy or teacherAgreement")
        return self


class BoundingBox(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    bbox_2d: tuple[float, float, float, float] = Field(alias="bbox2d")

    @model_validator(mode="after")
    def check_order(self) -> BoundingBox:
        left, top, right, bottom = self.bbox_2d
        if min(left, top, right, bottom) < 0:
            raise ValueError("bbox2d must not contain negative coordinates")
        if right <= left or bottom <= top:
            raise ValueError("bbox2d must be ordered as left, top, right, bottom")
        return self


class GeometryAnnotation(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    bbox: BoundingBox | None = None
    mask_path: str | None = Field(default=None, alias="maskPath")
    track_id: int | None = Field(default=None, alias="trackId")


class DistillationSample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: str = Field(alias="schemaVersion", min_length=1)
    sample_id: str = Field(alias="sampleId", min_length=1)
    image_path: str = Field(alias="imagePath", min_length=1)
    attributes: CandidateAttributes
    decision: Decision
    confidence: float = Field(ge=0, le=1)
    provenance: Provenance
    geometry: GeometryAnnotation | None = None


class DistillationTarget(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    sample_id: str = Field(alias="sampleId", min_length=1)
    decision: Decision
    attributes: CandidateAttributes
    confidence: float = Field(ge=0, le=1)


class QwenTurn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    sender: Literal["human", "gpt"] = Field(alias="from")
    value: str = Field(min_length=1)


class QwenRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    image: str = Field(min_length=1)
    conversations: tuple[QwenTurn, QwenTurn]


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as image_file:
        for chunk in iter(lambda: image_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_distillation_samples(path: Path) -> tuple[DistillationSample, ...]:
    samples: list[DistillationSample] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            samples.append(DistillationSample.model_validate_json(line))
        except ValueError as error:
            raise DistillationDataError(
                f"invalid distillation record at {path}:{line_number}: {error}"
            ) from error
    if not samples:
        raise DistillationDataError(f"no records found in {path}")
    return tuple(samples)


def to_qwen_record(
    sample: DistillationSample,
    image_root: Path,
    verify_hash: bool = True,
) -> QwenRecord:
    root = image_root.expanduser().resolve(strict=True)
    image_path = validate_local_image(sample.image_path, root)
    if verify_hash and file_sha256(image_path) != sample.provenance.source_hash:
        raise DistillationDataError(f"source hash mismatch for {sample.sample_id}")
    if sample.provenance.approval_status != "approved" and not sample.provenance.teacher_agreement:
        raise DistillationDataError(
            f"distillation sample {sample.sample_id} is not approved for training"
        )
    relative_image = image_path.relative_to(root).as_posix()
    answer = DistillationTarget(
        sampleId=sample.sample_id,
        decision=sample.decision,
        attributes=sample.attributes,
        confidence=sample.confidence,
    )
    prompt = (
        "<image>\n"
        "Inspect the object texture and include texture as an array in the JSON output. "
        "\uac1d\uccb4\uc758 \uc0c9\uc0c1, \ubcf5\uc7a5, \uac1d\uccb4 \uc18d\uc131\uacfc "
        "\ud6c4\ubcf4 \ud310\uc815\uc744 JSON\uc73c\ub85c \ucd9c\ub825\ud558\ub77c."
    )
    return QwenRecord(
        image=relative_image,
        conversations=(
            QwenTurn.model_validate({"from": "human", "value": prompt}),
            QwenTurn.model_validate(
                {"from": "gpt", "value": answer.model_dump_json(by_alias=True)}
            ),
        ),
    )


def write_qwen_jsonl(records: tuple[QwenRecord, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record.model_dump_json(by_alias=True) + "\n" for record in records),
        encoding="utf-8",
    )


def write_distillation_jsonl(records: tuple[DistillationSample, ...], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(record.model_dump_json(by_alias=True) + "\n" for record in records),
        encoding="utf-8",
    )

