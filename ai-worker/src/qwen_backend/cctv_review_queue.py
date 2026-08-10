from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .cctv_training_contract import CCTVTrainingSample


class ReviewQueueError(ValueError):
    pass


class CCTVReviewQueueItem(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    schema_version: Literal["cctv-review-queue-item-v1"] = Field(alias="schemaVersion")
    review_id: str = Field(alias="reviewId", min_length=1)
    case_id: str = Field(alias="caseId", min_length=1)
    source_video_id: str = Field(alias="sourceVideoId", min_length=1)
    camera_id: str = Field(alias="cameraId", min_length=1)
    sequence_id: str = Field(alias="sequenceId", min_length=1)
    source_track_id: str = Field(alias="sourceTrackId", min_length=1)
    condition_group_id: str = Field(alias="conditionGroupId", min_length=1)
    timestamp_ms: int = Field(alias="timestampMs", ge=0)
    source_frame_path: str = Field(alias="sourceFramePath", min_length=1)
    crop_path: str = Field(alias="cropPath", min_length=1)
    source_frame_sha256: str | None = Field(default=None, alias="sourceFrameSha256")
    crop_sha256: str | None = Field(default=None, alias="cropSha256")
    augmentation_count: int = Field(alias="augmentationCount", ge=1)
    target_role: str = Field(alias="targetRole", min_length=1)
    identity_group_id: str | None = Field(default=None, alias="identityGroupId")
    label_status: Literal["needs_human_review"] = Field(alias="labelStatus")
    labels: dict[str, tuple[str, ...]]
    training_eligible: Literal[False] = Field(alias="trainingEligible")
    approval_status: Literal["unreviewed"] = Field(alias="approvalStatus")
    identity_review_status: Literal["unreviewed"] = Field(alias="identityReviewStatus")
    teacher_agreement: Literal[False] = Field(alias="teacherAgreement")
    teacher_source_kind: Literal["none"] = Field(alias="teacherSourceKind")
    teacher_terms_status: Literal["not_applicable"] = Field(alias="teacherTermsStatus")
    label_provenance: Literal["none"] = Field(alias="labelProvenance")
    review_notes: tuple[str, ...] = Field(default=(), alias="reviewNotes")


def build_review_queue(
    samples: tuple[CCTVTrainingSample, ...],
) -> tuple[CCTVReviewQueueItem, ...]:
    if not samples:
        raise ReviewQueueError("review queue cannot be built from an empty manifest")

    grouped: dict[str, list[CCTVTrainingSample]] = defaultdict(list)
    for sample in samples:
        grouped[_frame_key(sample)].append(sample)

    queue: list[CCTVReviewQueueItem] = []
    review_ids: set[str] = set()
    for frame_key, grouped_samples in sorted(grouped.items()):
        originals = [sample for sample in grouped_samples if sample.augmentation == "original"]
        if not originals:
            raise ReviewQueueError(
                f"source frame {frame_key} has augmented rows but no original row"
            )
        if len(originals) != 1:
            raise ReviewQueueError(f"source frame {frame_key} has duplicate original rows")
        augmentations = [sample.augmentation for sample in grouped_samples]
        if len(set(augmentations)) != len(augmentations):
            raise ReviewQueueError(f"source frame {frame_key} has duplicate augmentation rows")
        original = originals[0]
        _validate_group_consistency(frame_key, original, grouped_samples)
        item = CCTVReviewQueueItem(
                schemaVersion="cctv-review-queue-item-v1",
                reviewId=_review_id(original),
                caseId=original.case_id,
                sourceVideoId=original.source_video_id,
                cameraId=original.camera_id,
                sequenceId=original.sequence_id,
                sourceTrackId=original.source_track_id,
                conditionGroupId=original.condition_group_id,
                timestampMs=original.timestamp_ms,
                sourceFramePath=original.source_frame_path,
                cropPath=original.crop_path,
                sourceFrameSha256=original.source_frame_sha256,
                cropSha256=original.crop_sha256,
                augmentationCount=len(grouped_samples),
                targetRole=original.target_role,
                identityGroupId=original.identity_group_id,
                labelStatus="needs_human_review",
                labels={
                    "color": (),
                    "clothing": (),
                    "texture": (),
                    "quality": (),
                    "occlusion": (),
                },
                trainingEligible=False,
                approvalStatus="unreviewed",
                identityReviewStatus="unreviewed",
                teacherAgreement=False,
                teacherSourceKind="none",
                teacherTermsStatus="not_applicable",
                labelProvenance="none",
                reviewNotes=(
                    "human review required before any training use",
                    "augmentation labels will be inherited only after original approval",
                ),
            )
        if item.review_id in review_ids:
            raise ReviewQueueError(f"duplicate reviewId generated: {item.review_id}")
        review_ids.add(item.review_id)
        queue.append(item)
    return tuple(queue)


def _frame_key(sample: CCTVTrainingSample) -> str:
    return "|".join(
        (
            sample.case_id,
            sample.source_video_id,
            sample.camera_id,
            sample.sequence_id,
            sample.source_track_id,
            sample.source_frame_path,
            str(sample.timestamp_ms),
        )
    )


def _review_id(sample: CCTVTrainingSample) -> str:
    digest = hashlib.sha256(_frame_key(sample).encode("utf-8")).hexdigest()[:12]
    return (
        f"{sample.case_id}/{sample.source_video_id}/{sample.source_track_id}/"
        f"{sample.timestamp_ms:012d}/{digest}"
    )


def _validate_group_consistency(
    frame_key: str,
    original: CCTVTrainingSample,
    grouped_samples: list[CCTVTrainingSample],
) -> None:
    for sample in grouped_samples:
        for field_name, original_value, sample_value in (
            ("caseId", original.case_id, sample.case_id),
            ("sourceVideoId", original.source_video_id, sample.source_video_id),
            ("cameraId", original.camera_id, sample.camera_id),
            ("sequenceId", original.sequence_id, sample.sequence_id),
            ("sourceTrackId", original.source_track_id, sample.source_track_id),
            ("conditionGroupId", original.condition_group_id, sample.condition_group_id),
            ("timestampMs", original.timestamp_ms, sample.timestamp_ms),
            ("sourceFramePath", original.source_frame_path, sample.source_frame_path),
            ("sourceFrameSha256", original.source_frame_sha256, sample.source_frame_sha256),
        ):
            if original_value != sample_value:
                raise ReviewQueueError(
                    f"source frame {frame_key} has inconsistent {field_name} metadata"
                )

