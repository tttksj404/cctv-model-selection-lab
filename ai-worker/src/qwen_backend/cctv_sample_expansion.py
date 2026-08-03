from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError

CropBox = tuple[int, int, int, int]
AugmentationName = Literal[
    "original",
    "brightness_low",
    "brightness_high",
    "contrast_low",
    "contrast_high",
    "blur",
    "low_resolution",
]
AttributeValue: TypeAlias = str | tuple[str, ...]


class SampleExpansionError(ValueError):
    pass


class DraftFrame(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True, frozen=True)

    schema_version: str = Field(alias="schemaVersion", min_length=1)
    case_id: str = Field(alias="caseId", min_length=1)
    video_id: str = Field(alias="videoId", min_length=1)
    camera_id: str = Field(alias="cameraId", min_length=1)
    condition_group_id: str = Field(alias="conditionGroupId", min_length=1)
    sequence_id: str = Field(alias="sequenceId", min_length=1)
    track_id: str = Field(alias="trackId", min_length=1)
    split: str = Field(min_length=1)
    target_role: str = Field(alias="targetRole", min_length=1)
    identity_group_id: str | None = Field(default=None, alias="identityGroupId")
    frame_path: str = Field(alias="framePath", min_length=1)
    timestamp_ms: int = Field(alias="timestampMs", ge=0)
    bbox: tuple[float, float, float, float]
    mask_path: str | None = Field(default=None, alias="maskPath")
    quality: float | None = Field(default=None, ge=0.0, le=1.0)
    quality_flags: tuple[str, ...] = Field(default=(), alias="qualityFlags")
    attributes: dict[str, AttributeValue] = Field(default_factory=dict)
    attribute_evidence_frame_ids: tuple[str, ...] = Field(
        default=(), alias="attributeEvidenceFrameIds"
    )


class ExpandedSample(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    schema_version: Literal["cctv-attribute-sample-v1"] = Field(alias="schemaVersion")
    sample_id: str = Field(alias="sampleId", min_length=1)
    case_id: str = Field(alias="caseId", min_length=1)
    source_frame_path: str = Field(alias="sourceFramePath", min_length=1)
    source_frame_sha256: str | None = Field(default=None, alias="sourceFrameSha256")
    source_video_id: str = Field(alias="sourceVideoId", min_length=1)
    camera_id: str = Field(alias="cameraId", min_length=1)
    sequence_id: str = Field(alias="sequenceId", min_length=1)
    source_track_id: str = Field(alias="sourceTrackId", min_length=1)
    condition_group_id: str = Field(alias="conditionGroupId", min_length=1)
    source_split: str = Field(alias="sourceSplit", min_length=1)
    timestamp_ms: int = Field(alias="timestampMs", ge=0)
    split: Literal["unassigned"]
    crop_path: str = Field(alias="cropPath", min_length=1)
    crop_sha256: str | None = Field(default=None, alias="cropSha256")
    augmentation: AugmentationName
    identity_group_id: None = Field(default=None, alias="identityGroupId")
    target_role: Literal["unknown"] = Field(default="unknown", alias="targetRole")
    label_status: Literal["needs_human_review"] = Field(alias="labelStatus")
    labels: dict[str, tuple[str, ...]]
    source_quality: float | None = Field(default=None, alias="sourceQuality")
    source_quality_flags: tuple[str, ...] = Field(default=(), alias="sourceQualityFlags")
    source_attributes: dict[str, AttributeValue] = Field(
        default_factory=dict, alias="sourceAttributes"
    )
    attribute_evidence_frame_ids: tuple[str, ...] = Field(
        default=(), alias="attributeEvidenceFrameIds"
    )
    training_eligible: Literal[False] = Field(alias="trainingEligible")
    approval_status: Literal["unreviewed"] = Field(alias="approvalStatus")
    identity_review_status: Literal["unreviewed"] = Field(alias="identityReviewStatus")
    teacher_agreement: Literal[False] = Field(alias="teacherAgreement")
    teacher_source_kind: Literal["none"] = Field(alias="teacherSourceKind")
    teacher_model: None = Field(default=None, alias="teacherModel")
    teacher_terms_status: Literal["not_applicable"] = Field(alias="teacherTermsStatus")
    label_provenance: Literal["none"] = Field(alias="labelProvenance")
    review_evidence_path: None = Field(default=None, alias="reviewEvidencePath")
    review_evidence_sha256: None = Field(default=None, alias="reviewEvidenceSha256")
    teacher_evidence_path: None = Field(default=None, alias="teacherEvidencePath")
    teacher_evidence_sha256: None = Field(default=None, alias="teacherEvidenceSha256")


class ExpansionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cctv-attribute-expansion-summary-v1"]
    status: Literal["unreviewed_teacher_ready"]
    source_rows: int
    expanded_rows: int
    augmentations: tuple[AugmentationName, ...]
    source_videos: tuple[str, ...]
    source_split_policy: Literal["preserved_in_source_split_unassigned_until_review"]
    identity_labels_available: Literal[False]
    track_heldout_metrics_eligible: Literal[False]
    training_eligible: Literal[False]


def augmentation_names() -> tuple[AugmentationName, ...]:
    return (
        "original",
        "brightness_low",
        "brightness_high",
        "contrast_low",
        "contrast_high",
        "blur",
        "low_resolution",
    )


def crop_box_for_frame(
    image_size: tuple[int, int], bbox: tuple[float, float, float, float], margin: float
) -> CropBox:
    if len(image_size) != 2 or min(image_size) <= 0:
        raise SampleExpansionError("image size must be positive")
    if not 0.0 <= margin <= 0.25:
        raise SampleExpansionError("crop margin must be between 0 and 0.25")
    width, height = image_size
    x1, y1, x2, y2 = bbox
    box_width = max(1.0, x2 - x1)
    box_height = max(1.0, y2 - y1)
    left = max(0, round(x1 - box_width * margin))
    top = max(0, round(y1 - box_height * margin))
    right = min(width, round(x2 + box_width * margin))
    bottom = min(height, round(y2 + box_height * margin))
    if right <= left or bottom <= top:
        raise SampleExpansionError("bbox does not intersect image")
    return left, top, right, bottom


def read_draft_manifest(path: Path) -> tuple[DraftFrame, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise SampleExpansionError(f"cannot read draft manifest: {path}") from error
    rows: list[DraftFrame] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            rows.append(DraftFrame.model_validate_json(line))
        except ValidationError as error:
            raise SampleExpansionError(
                f"invalid draft row at line {line_number}: {path}"
            ) from error
    if not rows:
        raise SampleExpansionError("draft manifest contains no rows")
    return tuple(rows)


def make_sample(
    row: DraftFrame,
    source_frame_path: Path,
    crop_path: Path,
    augmentation: AugmentationName,
    workspace: Path,
    index: int,
) -> ExpandedSample:
    crop_relative = crop_path.resolve().relative_to(workspace.resolve()).as_posix()
    frame_relative = source_frame_path.resolve().relative_to(workspace.resolve()).as_posix()
    return ExpandedSample(
        schemaVersion="cctv-attribute-sample-v1",
        sampleId=f"{row.video_id}-{index:06d}-{augmentation}",
        caseId=row.case_id,
        sourceFramePath=frame_relative,
        sourceFrameSha256=_sha256_file(source_frame_path),
        sourceVideoId=row.video_id,
        cameraId=row.camera_id,
        sequenceId=row.sequence_id,
        sourceTrackId=row.track_id,
        conditionGroupId=row.condition_group_id,
        sourceSplit=row.split,
        timestampMs=row.timestamp_ms,
        split="unassigned",
        cropPath=crop_relative,
        cropSha256=_sha256_file(crop_path),
        augmentation=augmentation,
        identityGroupId=None,
        targetRole="unknown",
        labelStatus="needs_human_review",
        labels={},
        sourceQuality=row.quality,
        sourceQualityFlags=row.quality_flags,
        sourceAttributes=row.attributes,
        attributeEvidenceFrameIds=row.attribute_evidence_frame_ids,
        trainingEligible=False,
        approvalStatus="unreviewed",
        identityReviewStatus="unreviewed",
        teacherAgreement=False,
        teacherSourceKind="none",
        teacherModel=None,
        teacherTermsStatus="not_applicable",
        labelProvenance="none",
        reviewEvidencePath=None,
        reviewEvidenceSha256=None,
        teacherEvidencePath=None,
        teacherEvidenceSha256=None,
    )


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
