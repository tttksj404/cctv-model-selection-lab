from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import ClassVar, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from qwen_backend.candidate_runtime import CandidateRuntimeResponse, RuntimeCandidate

INTERNAL_RECORDING_ANALYSIS_JOBS_PATH: Final = "/api/v1/internal/recording-analysis-jobs"
WORKER_KEY_HEADER: Final = "X-Worker-Key"
WORKER_CLAIM_TOKEN_HEADER: Final = "X-Worker-Claim-Token"
MAX_UPLOAD_URL_CANDIDATES: Final = 100
MAX_RESULT_CANDIDATES: Final = 1_000
MAX_ERROR_MESSAGE_LENGTH: Final = 1_000


class WorkerModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class RabbitWorkerJobEvent(WorkerModel):
    """Routing-only event published by the central server's outbox."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )

    command_id: str = Field(min_length=1, max_length=100)
    event_type: Literal["RECORDING_ANALYSIS_JOB_CREATED"]
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)
    camera_code: str = Field(min_length=1, max_length=100)
    camera_name: str = Field(min_length=1, max_length=255)
    recording_object_key: str = Field(min_length=1, max_length=500)
    attempt: int = Field(ge=1, le=100)
    occurred_at: datetime


class RecordingAnalysisClaim(WorkerModel):
    job_id: int = Field(gt=0)
    status: Literal["RUNNING"]
    attempt: int = Field(ge=1, le=100)
    duplicate: bool
    started_at: datetime
    claimed_by: str = Field(min_length=1, max_length=100)
    claim_expires_at: datetime
    lease_token: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_lease_shape(self) -> RecordingAnalysisClaim:
        if self.duplicate and self.lease_token is not None:
            raise ValueError("duplicate claim must not return leaseToken")
        if not self.duplicate and self.lease_token is None:
            raise ValueError("non-duplicate claim requires leaseToken")
        return self


class RecordingAnalysisTarget(WorkerModel):
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    search_condition_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)
    camera_code: str = Field(min_length=1, max_length=100)
    camera_name: str = Field(min_length=1, max_length=255)
    recording_object_key: str = Field(min_length=1, max_length=500)
    recording_download_url: str = Field(min_length=1, max_length=4_000)
    recording_start: datetime
    recording_end: datetime
    prompt: str = Field(max_length=4_000)
    exclusion_prompt: str | None = Field(default=None, max_length=4_000)
    search_start: datetime | None = None
    search_end: datetime | None = None
    search_area: str | None = Field(default=None, max_length=1_000)
    search_from_ms: int = Field(ge=0)
    search_to_ms: int = Field(gt=0)
    attempt: int = Field(ge=1, le=100)

    @field_validator("recording_download_url")
    @classmethod
    def validate_download_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("recordingDownloadUrl must use http or https")
        return value

    @model_validator(mode="after")
    def validate_time_window(self) -> RecordingAnalysisTarget:
        if self.recording_start >= self.recording_end:
            raise ValueError("recordingStart must be earlier than recordingEnd")
        if self.search_from_ms >= self.search_to_ms:
            raise ValueError("searchFromMs must be earlier than searchToMs")
        recording_duration_ms = int(
            (self.recording_end - self.recording_start).total_seconds() * 1_000
        )
        if self.search_to_ms > recording_duration_ms:
            raise ValueError("searchToMs must fall within the recording")
        if self.search_start is not None and self.search_end is not None:
            if self.search_start > self.search_end:
                raise ValueError("searchStart must not be later than searchEnd")
        return self


class RecordingAnalysisWorkerHeartbeat(WorkerModel):
    job_id: int = Field(gt=0)
    status: Literal["RUNNING"]
    claim_expires_at: datetime


class RecordingAnalysisUploadObject(WorkerModel):
    object_key: str = Field(min_length=1, max_length=500)
    upload_url: str = Field(min_length=1, max_length=4_000)
    content_type: Literal["image/jpeg", "image/png"]

    @field_validator("upload_url")
    @classmethod
    def validate_upload_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("uploadUrl must use http or https")
        return value


class RecordingAnalysisEvidenceUpload(WorkerModel):
    track_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame: RecordingAnalysisUploadObject
    crop: RecordingAnalysisUploadObject


class RecordingAnalysisUploadUrlRequestCandidate(WorkerModel):
    track_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame_content_type: Literal["image/jpeg", "image/png"]
    crop_content_type: Literal["image/jpeg", "image/png"]


class RecordingAnalysisUploadUrlRequest(WorkerModel):
    candidates: tuple[RecordingAnalysisUploadUrlRequestCandidate, ...] = Field(
        min_length=1,
        max_length=MAX_UPLOAD_URL_CANDIDATES,
    )

    @model_validator(mode="after")
    def validate_unique_track_ids(self) -> RecordingAnalysisUploadUrlRequest:
        track_ids = {candidate.track_id for candidate in self.candidates}
        if len(track_ids) != len(self.candidates):
            raise ValueError("upload URL request candidates must have unique trackId values")
        return self


class RecordingAnalysisUploadUrls(WorkerModel):
    attempt: int = Field(ge=1, le=100)
    candidates: tuple[RecordingAnalysisEvidenceUpload, ...] = Field(
        max_length=MAX_UPLOAD_URL_CANDIDATES
    )
    expires_in_seconds: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_unique_track_ids(self) -> RecordingAnalysisUploadUrls:
        track_ids = {candidate.track_id for candidate in self.candidates}
        if len(track_ids) != len(self.candidates):
            raise ValueError("upload URL candidates must have unique trackId values")
        return self


class RecordingAnalysisBoundingBox(WorkerModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class RecordingAnalysisResultCandidate(WorkerModel):
    track_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    detected_at: datetime
    similarity: float = Field(ge=0.0, le=1.0)
    frame_object_key: str = Field(min_length=1, max_length=500)
    crop_object_key: str = Field(min_length=1, max_length=500)
    bounding_box: RecordingAnalysisBoundingBox


class RecordingAnalysisResult(WorkerModel):
    result_id: str = Field(min_length=1, max_length=255)
    candidates: tuple[RecordingAnalysisResultCandidate, ...] = Field(
        max_length=MAX_RESULT_CANDIDATES
    )

    @model_validator(mode="after")
    def validate_unique_track_ids(self) -> RecordingAnalysisResult:
        track_ids = {candidate.track_id for candidate in self.candidates}
        if len(track_ids) != len(self.candidates):
            raise ValueError("result candidates must have unique trackId values")
        return self


class RecordingAnalysisFailureRequest(WorkerModel):
    result_id: str = Field(min_length=1, max_length=255)
    error_code: str = Field(min_length=1, max_length=100)
    error_message: str | None = Field(default=None, max_length=MAX_ERROR_MESSAGE_LENGTH)


class WorkerResponseModel(WorkerModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )


class RecordingAnalysisCompletion(WorkerResponseModel):
    job_id: int = Field(gt=0)
    result_id: str = Field(min_length=1, max_length=255)
    status: Literal["SUCCEEDED", "FAILED"]
    duplicate: bool


class RecordingAnalysisFailure(WorkerResponseModel):
    job_id: int = Field(gt=0)
    result_id: str = Field(min_length=1, max_length=255)
    status: Literal["FAILED"]
    attempt: int = Field(ge=1, le=100)
    duplicate: bool


def failure_result_id(*, worker_id: str, job_id: int, attempt: int) -> str:
    """Build an idempotency key for a terminal failure callback."""

    return f"{worker_id}:{job_id}:{attempt}:failure"


def result_from_runtime(
    response: CandidateRuntimeResponse,
    target: RecordingAnalysisTarget,
    *,
    worker_id: str,
    evidence_by_track_id: Mapping[str, RecordingAnalysisEvidenceUpload],
) -> RecordingAnalysisResult:
    """Convert local runtime output into the central server's persisted-result contract."""

    candidates = tuple(
        _result_candidate(candidate, target, evidence_by_track_id)
        for candidate in response.candidates
    )
    return RecordingAnalysisResult(
        result_id=f"{worker_id}:{target.job_id}:{target.attempt}",
        candidates=candidates,
    )


def _result_candidate(
    candidate: RuntimeCandidate,
    target: RecordingAnalysisTarget,
    evidence_by_track_id: Mapping[str, RecordingAnalysisEvidenceUpload],
) -> RecordingAnalysisResultCandidate:
    if (
        candidate.frame_offset_ms < target.search_from_ms
        or candidate.frame_offset_ms >= target.search_to_ms
    ):
        raise ValueError("runtime candidate falls outside the central search window")
    evidence = evidence_by_track_id.get(candidate.candidate_key)
    if evidence is None:
        raise ValueError("runtime candidate has no uploaded evidence")
    return RecordingAnalysisResultCandidate(
        track_id=candidate.candidate_key,
        detected_at=target.recording_start + timedelta(milliseconds=candidate.frame_offset_ms),
        similarity=candidate.similarity,
        frame_object_key=evidence.frame.object_key,
        crop_object_key=evidence.crop.object_key,
        bounding_box=RecordingAnalysisBoundingBox(
            x=candidate.bounding_box.x,
            y=candidate.bounding_box.y,
            width=candidate.bounding_box.width,
            height=candidate.bounding_box.height,
        ),
    )
