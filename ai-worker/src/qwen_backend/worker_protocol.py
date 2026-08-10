from __future__ import annotations

import re
from collections.abc import Mapping
from datetime import datetime, timedelta
from typing import Any, ClassVar, Final, Literal, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    field_validator,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel

from qwen_backend.candidate_runtime import CandidateRuntimeResponse, RuntimeCandidate

INTERNAL_RECORDING_ANALYSIS_JOBS_PATH: Final = "/api/v1/internal/recording-analysis-jobs"
DEVICE_RECORDING_ANALYSIS_JOBS_PATH: Final = "/api/v1/device/recording-analysis-jobs"
DEVICE_AI_SEARCH_JOBS_PATH: Final = "/api/v1/device/ai/jobs"
WORKER_KEY_HEADER: <redacted>
DEVICE_KEY_HEADER: <redacted>
WORKER_CLAIM_TOKEN_HEADER: <redacted>
MAX_UPLOAD_URL_CANDIDATES: Final = 100
MAX_RESULT_CANDIDATES: Final = 1_000
MAX_ERROR_MESSAGE_LENGTH: Final = 1_000
DEVICE_KEY_PATTERN: <redacted>


def _parse_wire_datetime(value: object) -> datetime:
    """Parse a JSON timestamp while keeping the worker contract timezone-aware."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    else:
        raise TypeError("timestamp must be a string or datetime")
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include timezone information")
    return parsed


class WorkerModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


class RabbitWorkerJobEvent(WorkerModel):
    """Routing-only event published by the central server's outbox.

    Legacy enriched fields are ignored during a rolling deployment, but the
    publisher contract emits only the four fields below.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )

    command_id: str = Field(min_length=1, max_length=100)
    event_type: Literal["RECORDING_ANALYSIS_JOB_CREATED"]
    job_id: int = Field(gt=0)
    occurred_at: datetime
    # The pre-Worker-API dev contract publishes the target together with the
    # Rabbit message.  Keep these optional so the routing-only contract remains
    # parseable when the central server is upgraded before the notebook.
    case_id: int | None = Field(default=None, gt=0)
    search_condition_id: int | None = Field(default=None, gt=0)
    recording_id: int | None = Field(default=None, gt=0)
    camera_id: int | None = Field(default=None, gt=0)
    camera_code: str | None = Field(default=None, min_length=1, max_length=100)
    camera_name: str | None = Field(default=None, min_length=1, max_length=255)
    recording_object_key: str | None = Field(default=None, min_length=1, max_length=500)
    recording_download_url: str | None = Field(default=None, max_length=4_000)
    recording_start: datetime | None = None
    recording_end: datetime | None = None
    prompt: str | None = Field(default=None, max_length=4_000)
    exclusion_prompt: str | None = Field(default=None, max_length=4_000)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    search_start: datetime | None = None
    search_end: datetime | None = None
    search_area: str | None = Field(default=None, max_length=1_000)
    search_from_ms: int | None = Field(default=None, ge=0)
    search_to_ms: int | None = Field(default=None, gt=0)
    attempt: int | None = Field(default=None, ge=1, le=100)

    @field_validator("recording_download_url")
    @classmethod
    def validate_recording_download_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("recordingDownloadUrl must use http or https")
        return value

    @model_validator(mode="after")
    def validate_legacy_time_window(self) -> RabbitWorkerJobEvent:
        if self.recording_start is not None and self.recording_end is not None:
            if self.recording_start >= self.recording_end:
                raise ValueError("recordingStart must be earlier than recordingEnd")
        if self.search_start is not None and self.search_end is not None:
            if self.search_start > self.search_end:
                raise ValueError("searchStart must not be later than searchEnd")
        return self

    @model_serializer(mode="wrap")
    def serialize_without_legacy_nulls(
        self,
        handler: SerializerFunctionWrapHandler,
    ) -> dict[str, Any]:
        payload = cast(dict[str, Any], handler(self))
        return {key: value for key, value in payload.items() if value is not None}


class DeviceBoundingBox(WorkerModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class DeviceDetection(WorkerModel):
    track_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    similarity: float = Field(ge=0.0, le=1.0)
    crop_object_key: str = Field(min_length=1, max_length=500)
    bounding_box: DeviceBoundingBox


class DeviceCandidateEvent(WorkerModel):
    """Payload accepted by the legacy Device Key recording-result endpoint."""

    case_id: int = Field(gt=0)
    camera_code: str = Field(min_length=1, max_length=100)
    event_id: str = Field(min_length=1, max_length=255)
    detected_at: datetime
    frame_object_key: str = Field(min_length=1, max_length=500)
    detections: tuple[DeviceDetection, ...] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def validate_unique_track_ids(self) -> DeviceCandidateEvent:
        track_ids = {detection.track_id for detection in self.detections}
        if len(track_ids) != len(self.detections):
            raise ValueError("device candidate detections must have unique trackId values")
        return self

    @classmethod
    def from_runtime(
        cls,
        event: RabbitWorkerJobEvent,
        *,
        track_id: str,
        similarity: float,
        frame_object_key: str,
        crop_object_key: str,
        detected_at: datetime,
        x: int,
        y: int,
        width: int,
        height: int,
    ) -> DeviceCandidateEvent:
        if event.case_id is None or event.camera_code is None:
            raise ValueError("legacy Rabbit event is missing caseId or cameraCode")
        return cls(
            case_id=event.case_id,
            camera_code=event.camera_code,
            event_id=f"analysis-{event.job_id}-attempt-{event.attempt or 1}",
            detected_at=detected_at,
            frame_object_key=frame_object_key,
            detections=(
                DeviceDetection(
                    track_id=track_id,
                    similarity=similarity,
                    crop_object_key=crop_object_key,
                    bounding_box=DeviceBoundingBox(x=x, y=y, width=width, height=height),
                ),
            ),
        )


class DeviceAiSearchJob(WorkerModel):
    """Current backend dev contract returned by ``POST /device/ai/jobs/claim``."""

    job_id: int = Field(gt=0)
    lease_token: str = Field(min_length=36, max_length=100)
    case_id: int = Field(gt=0)
    search_condition_id: int = Field(gt=0)
    recording_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)
    camera_name: str = Field(min_length=1, max_length=255)
    camera_address: str | None = Field(default=None, max_length=500)
    recording_object_key: str = Field(min_length=1, max_length=500)
    reference_photo_object_key: str | None = Field(default=None, max_length=500)
    recording_start: datetime
    recording_end: datetime
    prompt: str = Field(max_length=4_000)
    exclusion_prompt: str | None = Field(default=None, max_length=4_000)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    attempt: int = Field(default=1, ge=1, le=100)

    @model_validator(mode="after")
    def validate_recording_window(self) -> DeviceAiSearchJob:
        if self.recording_start >= self.recording_end:
            raise ValueError("recordingStart must be earlier than recordingEnd")
        return self


class DeviceAiClaimRequest(WorkerModel):
    model_key: str = Field(min_length=1, max_length=100)


class DeviceAiHeartbeatRequest(WorkerModel):
    lease_token: str = Field(min_length=36, max_length=100)


class DeviceAiCompleteCandidate(WorkerModel):
    candidate_key: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
    frame_offset_ms: int = Field(ge=0)
    similarity: float = Field(ge=0.0, le=1.0)
    crop_object_key: str = Field(min_length=1, max_length=500)
    clip_object_key: str | None = Field(default=None, max_length=500)
    bounding_box: DeviceBoundingBox
    attribute_summary: str | None = Field(default=None, max_length=2_000)


class DeviceAiCompleteRequest(WorkerModel):
    lease_token: str = Field(min_length=36, max_length=100)
    model_key: str = Field(min_length=1, max_length=100)
    candidates: tuple[DeviceAiCompleteCandidate, ...] = Field(max_length=100)


class DeviceAiFailureRequest(WorkerModel):
    lease_token: str = Field(min_length=36, max_length=100)
    error_code: str = Field(min_length=1, max_length=100)
    error_message: str = Field(min_length=1, max_length=1_000)
    retryable: bool = True


class DeviceAiMutationResponse(WorkerModel):
    job_id: int = Field(gt=0)
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED"]
    result_count: int = Field(ge=0)


class RecordingAnalysisClaim(WorkerModel):
    # Claim responses are server-owned metadata.  Ignore additive fields from
    # a rolling backend deployment while keeping all required fields and state
    # invariants strict below.
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="ignore",
        frozen=True,
    )

    job_id: int = Field(gt=0)
    status: Literal["QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "CANCELLED"]
    attempt: int = Field(ge=1, le=100)
    disposition: (
        Literal[
            "CLAIMED",
            "LEASE_HELD",
            "LEASE_HELD_BY_SELF",
            "LEASE_HELD_BY_OTHER",
            "RETRY_PENDING",
            "TERMINAL",
        ]
        | None
    ) = None
    duplicate: bool | None = None
    started_at: datetime | None = None
    claimed_by: str | None = Field(default=None, min_length=1, max_length=100)
    claim_expires_at: datetime | None = None
    lease_token: str | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_duplicate_claim(cls, value: object) -> object:
        if not isinstance(value, Mapping):
            return value
        payload: dict[str, object] = dict(cast(Mapping[str, object], value))
        duplicate = payload.get("duplicate")
        if (
            "disposition" not in payload
            and payload.get("status") == "RUNNING"
            and isinstance(duplicate, bool)
        ):
            payload["disposition"] = "LEASE_HELD" if duplicate else "CLAIMED"
        return payload

    @model_validator(mode="after")
    def validate_lease_shape(self) -> RecordingAnalysisClaim:
        if self.disposition == "CLAIMED":
            if self.status != "RUNNING":
                raise ValueError("CLAIMED response requires RUNNING status")
        elif self.disposition in {"LEASE_HELD", "LEASE_HELD_BY_SELF", "LEASE_HELD_BY_OTHER"}:
            if self.status != "RUNNING" or self.lease_token is not None:
                raise ValueError("LEASE_HELD response requires RUNNING status without leaseToken")
        elif self.disposition == "RETRY_PENDING":
            if self.status != "QUEUED" or self.lease_token is not None:
                raise ValueError("RETRY_PENDING response requires QUEUED status without leaseToken")
        elif self.disposition == "TERMINAL":
            is_terminal = self.status in {"SUCCEEDED", "FAILED", "CANCELLED"}
            if not is_terminal or self.lease_token is not None:
                raise ValueError("TERMINAL response requires terminal status without leaseToken")
        else:
            raise ValueError("claim response requires disposition")
        return self


class RecordingAnalysisTarget(WorkerModel):
    job_id: int = Field(gt=0)
    case_id: int = Field(gt=0)
    search_condition_id: int | None = Field(default=None, gt=0)
    recording_id: int = Field(gt=0)
    camera_id: int = Field(gt=0)
    camera_code: str = Field(min_length=1, max_length=100)
    camera_name: str = Field(min_length=1, max_length=255)
    recording_object_key: str = Field(min_length=1, max_length=500)
    recording_download_url: str | None = Field(default=None, max_length=4_000)
    recording_download_url_expires_in_seconds: int | None = Field(default=None, gt=0)
    recording_file_size_bytes: int | None = Field(default=None, ge=0)
    recording_content_type: str | None = Field(default=None, min_length=1, max_length=255)
    # Optional additive fields: older central deployments omit the reference
    # photo and threshold, while newer deployments can unlock SOLIDER and an
    # explicit server-side cut-off without changing the worker callback shape.
    reference_photo_object_key: str | None = Field(default=None, max_length=500)
    reference_photo_download_url: str | None = Field(default=None, max_length=4_000)
    reference_photo_download_url_expires_in_seconds: int | None = Field(default=None, gt=0)
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    recording_start: datetime
    recording_end: datetime
    prompt: str = Field(max_length=4_000)
    exclusion_prompt: str | None = Field(default=None, max_length=4_000)
    search_start: datetime | None = None
    search_end: datetime | None = None
    analysis_start: datetime | None = None
    analysis_end: datetime | None = None
    search_area: str | None = Field(default=None, max_length=1_000)
    search_from_ms: int = Field(ge=0)
    search_to_ms: int = Field(gt=0)
    attempt: int = Field(ge=1, le=100)

    @field_validator("recording_download_url", "reference_photo_download_url")
    @classmethod
    def validate_download_url(cls, value: str | None) -> str | None:
        if value is not None and not value.startswith(("http://", "https://")):
            raise ValueError("download URLs must use http or https")
        return value

    @model_validator(mode="before")
    @classmethod
    def derive_analysis_window(cls, value: object) -> object:
        """Map the current worker API's timestamps to runtime frame offsets."""

        if not isinstance(value, Mapping):
            return value
        payload: dict[str, object] = dict(cast(Mapping[str, object], value))
        has_start_offset = "searchFromMs" in payload or "search_from_ms" in payload
        has_end_offset = "searchToMs" in payload or "search_to_ms" in payload
        if has_start_offset or has_end_offset:
            return payload

        analysis_start = payload.get("analysisStart", payload.get("analysis_start"))
        analysis_end = payload.get("analysisEnd", payload.get("analysis_end"))
        recording_start = payload.get("recordingStart", payload.get("recording_start"))
        if analysis_start is None or analysis_end is None or recording_start is None:
            return payload
        try:
            analysis_start_at = _parse_wire_datetime(analysis_start)
            analysis_end_at = _parse_wire_datetime(analysis_end)
            recording_start_at = _parse_wire_datetime(recording_start)
        except (TypeError, ValueError) as exception:
            raise ValueError("analysis timestamps must use ISO-8601 datetimes") from exception
        payload["searchFromMs"] = round(
            (analysis_start_at - recording_start_at).total_seconds() * 1_000
        )
        payload["searchToMs"] = round(
            (analysis_end_at - recording_start_at).total_seconds() * 1_000
        )
        return payload

    @model_validator(mode="after")
    def validate_time_window(self) -> RecordingAnalysisTarget:
        if self.recording_start >= self.recording_end:
            raise ValueError("recordingStart must be earlier than recordingEnd")
        if self.search_from_ms >= self.search_to_ms:
            raise ValueError("searchFromMs must be earlier than searchToMs")
        recording_duration_ms = round(
            (self.recording_end - self.recording_start).total_seconds() * 1_000
        )
        if self.search_to_ms > recording_duration_ms:
            raise ValueError("searchToMs must fall within the recording")
        if self.search_start is not None and self.search_end is not None:
            if self.search_start > self.search_end:
                raise ValueError("searchStart must not be later than searchEnd")
        if (self.analysis_start is None) != (self.analysis_end is None):
            raise ValueError("analysisStart and analysisEnd must be provided together")
        if self.analysis_start is not None and self.analysis_end is not None:
            if self.analysis_start >= self.analysis_end:
                raise ValueError("analysisStart must be earlier than analysisEnd")
            expected_from_ms = round(
                (self.analysis_start - self.recording_start).total_seconds() * 1_000
            )
            expected_to_ms = round(
                (self.analysis_end - self.recording_start).total_seconds() * 1_000
            )
            if (self.search_from_ms, self.search_to_ms) != (expected_from_ms, expected_to_ms):
                raise ValueError("analysis timestamps do not match the search window")
        return self

    @property
    def resolved_search_window_ms(self) -> tuple[int, int]:
        """Expose the validated original-recording window used by local inference."""

        return self.search_from_ms, self.search_to_ms


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

