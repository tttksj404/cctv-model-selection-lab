from __future__ import annotations

import hashlib
import json
import string
import unicodedata
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Literal, TypeAlias

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .cctv_sample_expansion import AttributeValue, AugmentationName

_VALID_SPLITS = frozenset(
    {"train", "validation", "test_landscape", "test_portrait_fisheye"}
)
_TEST_ONLY_SPLITS = frozenset({"test_landscape", "test_portrait_fisheye"})
_REVIEWED_LABEL_STATUSES = frozenset({"human_reviewed", "teacher_agreed"})
_VALID_TARGET_ROLES = frozenset({"target", "distractor"})
_REQUIRED_LABEL_FIELDS = frozenset({"color", "clothing", "texture", "quality", "occlusion"})
_DEFAULT_CONDITION_HOLDOUTS = {
    "landscape_room": "test_landscape",
    "portrait_fisheye": "test_portrait_fisheye",
}
_SOURCE_SPLIT_ALLOWED = {
    "train": frozenset({"train"}),
    "validation": frozenset({"validation"}),
    "test": frozenset({"test_landscape", "test_portrait_fisheye"}),
}
_VALID_TEACHER_SOURCES = frozenset({"florence", "sonnet"})
JsonScalar: TypeAlias = str | int | float | bool | None
JsonValue: TypeAlias = JsonScalar | list["JsonValue"] | dict[str, "JsonValue"]


class TrainingManifestError(ValueError):
    pass


class CCTVTrainingSample(BaseModel):
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
    split: str = Field(min_length=1)
    crop_path: str = Field(alias="cropPath", min_length=1)
    crop_sha256: str | None = Field(default=None, alias="cropSha256")
    augmentation: AugmentationName
    timestamp_ms: int = Field(alias="timestampMs", ge=0)
    identity_group_id: str | None = Field(default=None, alias="identityGroupId")
    target_role: str = Field(alias="targetRole", min_length=1)
    label_status: str = Field(alias="labelStatus", min_length=1)
    labels: dict[str, tuple[str, ...]]
    source_quality: float | None = Field(default=None, alias="sourceQuality")
    source_quality_flags: tuple[str, ...] = Field(default=(), alias="sourceQualityFlags")
    source_attributes: dict[str, AttributeValue] = Field(
        default_factory=dict, alias="sourceAttributes"
    )
    attribute_evidence_frame_ids: tuple[str, ...] = Field(
        default=(), alias="attributeEvidenceFrameIds"
    )
    training_eligible: bool = Field(alias="trainingEligible")
    approval_status: str = Field(alias="approvalStatus", min_length=1)
    identity_review_status: str = Field(alias="identityReviewStatus", min_length=1)
    teacher_agreement: bool = Field(alias="teacherAgreement")
    teacher_source_kind: str = Field(alias="teacherSourceKind", min_length=1)
    teacher_model: str | None = Field(default=None, alias="teacherModel")
    teacher_terms_status: str = Field(alias="teacherTermsStatus", min_length=1)
    label_provenance: str = Field(alias="labelProvenance", min_length=1)
    review_evidence_path: str | None = Field(default=None, alias="reviewEvidencePath")
    review_evidence_sha256: str | None = Field(default=None, alias="reviewEvidenceSha256")
    teacher_evidence_path: str | None = Field(default=None, alias="teacherEvidencePath")
    teacher_evidence_sha256: str | None = Field(default=None, alias="teacherEvidenceSha256")


class TrainingManifestReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["cctv-attribute-training-report-v1"]
    status: Literal["valid", "blocked"]
    rows: int
    eligible_rows: int
    identity_groups: int
    tracks: int
    condition_splits: Mapping[str, tuple[str, ...]]
    error_count: int
    errors: tuple[str, ...]


def load_training_manifest(path: Path) -> tuple[CCTVTrainingSample, ...]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as error:
        raise TrainingManifestError(f"cannot read training manifest: {path}") from error
    samples: list[CCTVTrainingSample] = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line, object_pairs_hook=_reject_duplicate_keys)
            samples.append(CCTVTrainingSample.model_validate(payload))
        except (ValidationError, TrainingManifestError, json.JSONDecodeError) as error:
            raise TrainingManifestError(
                f"invalid training row at line {line_number}: {path}"
            ) from error
    if not samples:
        raise TrainingManifestError("training manifest contains no rows")
    return tuple(samples)


def validate_training_manifest(
    samples: Iterable[CCTVTrainingSample],
    condition_holdouts: Mapping[str, str] | None = None,
    max_errors: int = 20,
    temporal_embargo_ms: int = 30_000,
    workspace: Path | None = None,
) -> TrainingManifestReport:
    if temporal_embargo_ms < 0:
        raise TrainingManifestError("temporal embargo must be non-negative")
    rows = tuple(samples)
    holdouts = {
        _normalize_key(condition): split for condition, split in _DEFAULT_CONDITION_HOLDOUTS.items()
    }
    errors: list[str] = []
    if condition_holdouts is not None:
        for condition, split in condition_holdouts.items():
            condition_key = _normalize_key(condition)
            expected = holdouts.get(condition_key)
            if expected is not None:
                if split != expected:
                    errors.append(
                        f"condition {condition_key}: protected holdout cannot be changed"
                    )
                continue
            holdouts[condition_key] = split
    eligible = tuple(sample for sample in rows if sample.training_eligible)
    track_split: dict[str, str] = {}
    track_identity: dict[str, str] = {}
    identity_split: dict[str, set[str]] = {}
    condition_splits: dict[str, set[str]] = {}
    sample_ids: set[str] = set()
    path_splits: dict[str, str] = {}

    def add_error(message: str) -> None:
        errors.append(message)

    if eligible and workspace is None:
        add_error("workspace is required to validate training data paths")

    for sample in rows:
        sample_key = _normalize_key(sample.sample_id)
        if sample_key in sample_ids:
            add_error(f"{sample.sample_id}: duplicate sampleId")
        sample_ids.add(sample_key)
        _validate_data_paths(sample, workspace, path_splits, add_error)
        if not sample.training_eligible:
            add_error(f"{sample.sample_id}: trainingEligible=false")
            continue
        if sample.label_status not in _REVIEWED_LABEL_STATUSES:
            add_error(f"{sample.sample_id}: labelStatus is not reviewed")
        if sample.approval_status != "approved":
            add_error(f"{sample.sample_id}: approvalStatus is not approved")
        if sample.identity_review_status != "human_reviewed":
            add_error(f"{sample.sample_id}: identityReviewStatus is not human_reviewed")
        if sample.target_role not in _VALID_TARGET_ROLES:
            add_error(f"{sample.sample_id}: targetRole must be target or distractor")
        if sample.identity_group_id is None or not sample.identity_group_id.strip():
            add_error(f"{sample.sample_id}: identityGroupId is required")
        if sample.split not in _VALID_SPLITS:
            add_error(f"{sample.sample_id}: invalid split {sample.split}")
        elif sample.split != "train" and sample.augmentation != "original":
            add_error(f"{sample.sample_id}: non-train split must use original augmentation")
        source_split = _normalize_key(sample.source_split)
        allowed_splits = _SOURCE_SPLIT_ALLOWED.get(source_split)
        if allowed_splits is not None and sample.split not in allowed_splits:
            add_error(f"{sample.sample_id}: sourceSplit is inconsistent with split")
        missing_fields = _REQUIRED_LABEL_FIELDS.difference(sample.labels)
        empty_fields = {field for field in _REQUIRED_LABEL_FIELDS if not sample.labels.get(field)}
        if missing_fields or empty_fields:
            missing = ",".join(sorted(missing_fields | empty_fields))
            add_error(f"{sample.sample_id}: missing labels {missing}")
        for field in ("quality", "occlusion"):
            values = sample.labels.get(field, ())
            if values and values != ("unknown",):
                if len(values) != 1:
                    add_error(f"{sample.sample_id}: {field} must have one value")
                else:
                    try:
                        numeric_value = float(values[0])
                    except ValueError:
                        add_error(f"{sample.sample_id}: {field} must be a float in [0, 1]")
                    else:
                        if not 0.0 <= numeric_value <= 1.0:
                            add_error(f"{sample.sample_id}: {field} must be a float in [0, 1]")
        if sample.label_status == "human_reviewed":
            if sample.teacher_agreement:
                add_error(f"{sample.sample_id}: human_reviewed cannot set teacherAgreement")
            if sample.label_provenance != "human_review":
                add_error(f"{sample.sample_id}: human label provenance is invalid")
            if (
                sample.teacher_source_kind != "none"
                or sample.teacher_terms_status != "not_applicable"
            ):
                add_error(f"{sample.sample_id}: human label has teacher metadata")
        if sample.label_status == "teacher_agreed":
            if not sample.teacher_agreement:
                add_error(f"{sample.sample_id}: teacher_agreed requires teacherAgreement")
            if sample.teacher_source_kind not in _VALID_TEACHER_SOURCES:
                add_error(f"{sample.sample_id}: teacher source is invalid")
            if not sample.teacher_model:
                add_error(f"{sample.sample_id}: teacher model is required")
            if sample.teacher_terms_status != "approved":
                add_error(f"{sample.sample_id}: teacher terms are not approved")
            if sample.label_provenance != "teacher_agreement":
                add_error(f"{sample.sample_id}: teacher label provenance is invalid")
            if not sample.teacher_evidence_path or not _is_sha256(sample.teacher_evidence_sha256):
                add_error(f"{sample.sample_id}: teacher evidence is required")
        if not sample.review_evidence_path or not _is_sha256(sample.review_evidence_sha256):
            add_error(f"{sample.sample_id}: review evidence is required")
        if not _is_sha256(sample.source_frame_sha256):
            add_error(f"{sample.sample_id}: source frame hash is required")
        if not _is_sha256(sample.crop_sha256):
            add_error(f"{sample.sample_id}: crop hash is required")
        if (
            _normalize_key(sample.source_track_id) in track_split
            and track_split[_normalize_key(sample.source_track_id)] != sample.split
        ):
            add_error(f"{sample.sample_id}: sourceTrackId crosses split")
        if (
            _normalize_key(sample.source_track_id) in track_identity
            and track_identity[_normalize_key(sample.source_track_id)]
            != _normalize_key(sample.identity_group_id or "")
        ):
            add_error(f"{sample.sample_id}: sourceTrackId changes identityGroupId")
        identity_key = _normalize_key(sample.identity_group_id or "")
        if identity_key and identity_key in identity_split:
            known_splits = identity_split[identity_key]
            if sample.split not in known_splits and not (
                known_splits.issubset(_TEST_ONLY_SPLITS)
                and sample.split in _TEST_ONLY_SPLITS
            ):
                add_error(f"{sample.sample_id}: identityGroupId crosses split")
        track_key = _normalize_key(sample.source_track_id)
        track_split.setdefault(track_key, sample.split)
        track_identity.setdefault(track_key, identity_key)
        if identity_key:
            identity_split.setdefault(identity_key, set()).add(sample.split)
        condition_key = _normalize_key(sample.condition_group_id)
        condition_splits.setdefault(condition_key, set()).add(sample.split)

    for condition, expected_split in holdouts.items():
        actual = condition_splits.get(condition, set())
        if not actual:
            add_error(f"condition {condition}: no eligible rows")
        elif actual != {expected_split}:
            actual_text = ",".join(sorted(actual))
            add_error(f"condition {condition}: expected only {expected_split}, got {actual_text}")

    timeline: dict[tuple[str, str], list[tuple[int, str, str]]] = {}
    for sample in eligible:
        key = (_normalize_key(sample.case_id), _normalize_key(sample.source_video_id))
        timeline.setdefault(key, []).append((sample.timestamp_ms, sample.split, sample.sample_id))
    for key, entries in timeline.items():
        ordered = sorted(entries)
        for index, (timestamp_ms, split, sample_id) in enumerate(ordered):
            for previous_timestamp, previous_split, _ in ordered[:index]:
                if (
                    split != previous_split
                    and timestamp_ms - previous_timestamp < temporal_embargo_ms
                ):
                    add_error(
                        f"{sample_id}: temporal embargo violated for {key[1]} "
                        f"({previous_split}->{split})"
                    )

    visible_errors = tuple(errors[:max_errors])
    return TrainingManifestReport(
        schema_version="cctv-attribute-training-report-v1",
        status="valid" if not errors else "blocked",
        rows=len(rows),
        eligible_rows=len(eligible),
        identity_groups=len(identity_split),
        tracks=len(track_split),
        condition_splits={
            key: tuple(sorted(value)) for key, value in sorted(condition_splits.items())
        },
        error_count=len(errors),
        errors=visible_errors,
    )


def _reject_duplicate_keys(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    payload: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in payload:
            raise TrainingManifestError(f"duplicate JSON key: {key}")
        payload[key] = value
    return payload


def _normalize_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def _is_sha256(value: str | None) -> bool:
    return value is not None and len(value) == 64 and all(
        char in string.hexdigits for char in value
    )


def _validate_data_paths(
    sample: CCTVTrainingSample,
    workspace: Path | None,
    path_splits: dict[str, str],
    add_error: Callable[[str], None],
) -> None:
    if workspace is None:
        return
    root = workspace.resolve()
    for field_name, raw_path in (
        ("sourceFramePath", sample.source_frame_path),
        ("cropPath", sample.crop_path),
        ("reviewEvidencePath", sample.review_evidence_path),
        ("teacherEvidencePath", sample.teacher_evidence_path),
    ):
        if raw_path is None:
            continue
        candidate = Path(raw_path)
        try:
            resolved = (root / candidate).resolve()
            resolved.relative_to(root)
        except ValueError:
            add_error(f"{sample.sample_id}: {field_name} is outside workspace")
            continue
        if not resolved.is_file():
            add_error(f"{sample.sample_id}: {field_name} does not exist")
            continue
        if field_name in {"sourceFramePath", "cropPath"}:
            key = unicodedata.normalize("NFKC", str(resolved)).casefold()
            previous_split = path_splits.get(key)
            if previous_split is not None and previous_split != sample.split:
                add_error(f"{sample.sample_id}: {field_name} crosses split")
            path_splits.setdefault(key, sample.split)
            expected_hash = (
                sample.source_frame_sha256
                if field_name == "sourceFramePath"
                else sample.crop_sha256
            )
            actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if expected_hash != actual_hash:
                add_error(f"{sample.sample_id}: {field_name} hash mismatch")
        if field_name in {"reviewEvidencePath", "teacherEvidencePath"}:
            expected_hash = (
                sample.review_evidence_sha256
                if field_name == "reviewEvidencePath"
                else sample.teacher_evidence_sha256
            )
            actual_hash = hashlib.sha256(resolved.read_bytes()).hexdigest()
            if expected_hash != actual_hash:
                add_error(f"{sample.sample_id}: {field_name} hash mismatch")

