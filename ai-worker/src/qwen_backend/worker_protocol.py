from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from qwen_backend.candidate_runtime import CandidateRuntimeResponse, RuntimeCandidate

WORKER_PROTOCOL_VERSION = "eyesonu-ai-worker-v1"
RABBIT_WORKER_EVENT_VERSION = "eyesonu-ai-worker-event-v1"
WORKER_JOBS_PATH = "/api/v1/ai-worker/jobs"
WORKER_KEY_HEADER = "X-AI-Worker-Key"
WORKER_ID_HEADER = "X-AI-Worker-ID"
MAX_WORKER_CANDIDATES = 100
MAX_WORKER_ERROR_MESSAGE_LENGTH = 2_000


class WorkerModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class RabbitWorkerJobEvent(WorkerModel):
    """Broker payload containing routing metadata only, never person data or URLs."""

    schema_version: Literal["eyesonu-ai-worker-event-v1"] = RABBIT_WORKER_EVENT_VERSION
    event_id: str = Field(min_length=1, max_length=100)
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    attempt: int = Field(ge=1, le=100)
    occurred_at: datetime


class WorkerBoundingBox(WorkerModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class WorkerJob(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    search_condition_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    model_key: str = Field(min_length=1, max_length=100)
    camera_id: int = Field(gt=0)
    camera_name: str = Field(min_length=1, max_length=255)
    camera_address: str = Field(min_length=1, max_length=255)
    video_url: str = Field(min_length=1, max_length=4_000)
    reference_url: str | None = Field(default=None, max_length=4_000)
    recording_start: datetime
    recording_end: datetime
    prompt: str = Field(max_length=4_000)
    exclusion_prompt: str | None = Field(default=None, max_length=4_000)
    similarity_threshold: float = Field(ge=0.0, le=1.0)
    search_from_ms: int = Field(default=0, ge=0)
    search_to_ms: int | None = Field(default=None, gt=0)
    lease_expires_at: datetime

    @field_validator("video_url", "reference_url")
    @classmethod
    def validate_download_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("worker download URLs must use http or https")
        return value

    @model_validator(mode="after")
    def validate_recording_and_search_window(self) -> WorkerJob:
        if self.recording_start >= self.recording_end:
            raise ValueError("recordingStart must be earlier than recordingEnd")
        if self.search_to_ms is not None and self.search_from_ms >= self.search_to_ms:
            raise ValueError("searchFromMs must be earlier than searchToMs")
        return self


class WorkerClaimRequest(WorkerModel):
    worker_id: str = Field(min_length=1, max_length=100)
    model_key: str = Field(min_length=1, max_length=100)


class WorkerClaimResponse(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    job: WorkerJob | None = None
    lease_token: str | None = Field(default=None, min_length=1, max_length=200)
    lease_expires_at: datetime | None = None
    poll_after_ms: int = Field(default=0, ge=0, le=60_000)

    @model_validator(mode="after")
    def validate_claim_shape(self) -> WorkerClaimResponse:
        has_job = self.job is not None
        if has_job != (self.lease_token is not None and self.lease_expires_at is not None):
            raise ValueError("job and lease fields must be returned together")
        return self


class WorkerHeartbeatRequest(WorkerModel):
    worker_id: str = Field(min_length=1, max_length=100)
    lease_token: str = Field(min_length=1, max_length=200)


class WorkerHeartbeatResponse(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    job_id: int = Field(gt=0)
    status: Literal["RUNNING"]
    lease_expires_at: datetime


class WorkerCandidate(WorkerModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame_offset_ms: int = Field(ge=0)
    similarity: float = Field(ge=0.0, le=1.0)
    bounding_box: WorkerBoundingBox
    attribute_summary: str | None = Field(default=None, max_length=2_000)
    crop_object_key: str | None = Field(default=None, max_length=500)
    frame_object_key: str | None = Field(default=None, max_length=500)


class WorkerEvidenceUpload(WorkerModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame_object_key: str = Field(min_length=1, max_length=500)
    frame_upload_url: str = Field(min_length=1, max_length=4_000)
    crop_object_key: str = Field(min_length=1, max_length=500)
    crop_upload_url: str = Field(min_length=1, max_length=4_000)

    @field_validator("frame_upload_url", "crop_upload_url")
    @classmethod
    def validate_upload_url(cls, value: str) -> str:
        if not value.startswith(("http://", "https://")):
            raise ValueError("worker upload URLs must use http or https")
        return value


class WorkerEvidenceUploadResponse(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    job_id: int = Field(gt=0)
    attempt: int = Field(ge=1)
    expires_in_seconds: int = Field(ge=1)
    uploads: tuple[WorkerEvidenceUpload, ...] = Field(max_length=MAX_WORKER_CANDIDATES)

    @model_validator(mode="after")
    def validate_unique_candidate_keys(self) -> WorkerEvidenceUploadResponse:
        candidate_keys = {upload.candidate_key for upload in self.uploads}
        if len(candidate_keys) != len(self.uploads):
            raise ValueError("evidence upload candidateKey must be unique")
        return self


class WorkerResult(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    model_key: str = Field(min_length=1, max_length=100)
    candidates: tuple[WorkerCandidate, ...] = Field(max_length=MAX_WORKER_CANDIDATES)
    inference_duration_ms: int = Field(ge=0)


class WorkerCompleteRequest(WorkerModel):
    worker_id: str = Field(min_length=1, max_length=100)
    lease_token: str = Field(min_length=1, max_length=200)
    result: WorkerResult


class WorkerFailRequest(WorkerModel):
    worker_id: str = Field(min_length=1, max_length=100)
    lease_token: str = Field(min_length=1, max_length=200)
    error_code: str = Field(min_length=1, max_length=100)
    error_message: str = Field(min_length=1, max_length=MAX_WORKER_ERROR_MESSAGE_LENGTH)
    retryable: bool = False


class WorkerJobStatusResponse(WorkerModel):
    schema_version: Literal["eyesonu-ai-worker-v1"] = WORKER_PROTOCOL_VERSION
    job_id: int = Field(gt=0)
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    worker_id: str | None = None
    result_model_key: str | None = None
    result_digest: str | None = None


def _worker_candidate(
    candidate: RuntimeCandidate,
    evidence: WorkerEvidenceUpload | None,
) -> WorkerCandidate:
    return WorkerCandidate(
        candidate_key=candidate.candidate_key,
        frame_offset_ms=candidate.frame_offset_ms,
        similarity=candidate.similarity,
        bounding_box=WorkerBoundingBox(
            x=candidate.bounding_box.x,
            y=candidate.bounding_box.y,
            width=candidate.bounding_box.width,
            height=candidate.bounding_box.height,
        ),
        attribute_summary=candidate.attribute_summary,
        crop_object_key=None if evidence is None else evidence.crop_object_key,
        frame_object_key=None if evidence is None else evidence.frame_object_key,
    )


def worker_result_from_runtime(
    response: CandidateRuntimeResponse,
    inference_duration_ms: int,
    evidence_by_candidate_key: Mapping[str, WorkerEvidenceUpload] | None = None,
) -> WorkerResult:
    return WorkerResult(
        model_key=response.model_key,
        candidates=tuple(
            _worker_candidate(
                candidate,
                (
                    None
                    if evidence_by_candidate_key is None
                    else evidence_by_candidate_key.get(candidate.candidate_key)
                ),
            )
            for candidate in response.candidates
        ),
        inference_duration_ms=inference_duration_ms,
    )
