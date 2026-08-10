from __future__ import annotations

from datetime import datetime
from enum import StrEnum, unique
from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from .zone_topology import (
    CAMERA_POSITIONS,
    CAMERAS_PER_ZONE,
    JURISDICTION_ZONE_COUNT,
)

ZONE_SEARCH_SCHEMA_VERSION = "eyesonu-zone-search-v1"


class ZoneSearchModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
        frozen=True,
    )


@unique
class AnalysisMode(StrEnum):
    PARALLEL_ZONE_REPRESENTATIVES = "parallel_zone_representatives"


@unique
class SegmentOrder(StrEnum):
    NEWEST_FIRST = "newest_first"
    OLDEST_FIRST = "oldest_first"


@unique
class OperatorDecision(StrEnum):
    CONFIRMED_MATCH = "confirmed_match"
    REJECTED = "rejected"
    REVIEW_REQUIRED = "review_required"


@unique
class JetsonAction(StrEnum):
    ACTIVATE_CANDIDATE_ZONE = "activate_candidate_zone"
    AWAIT_OPERATOR_CONFIRMATION = "await_operator_confirmation"
    CONTINUE_ARCHIVE_SEARCH = "continue_archive_search"
    IGNORE_STALE_DECISION = "ignore_stale_decision"
    RECORD_HISTORICAL_TRACE = "record_historical_trace"


@unique
class ScoreKind(StrEnum):
    CALIBRATED_MATCH_PROBABILITY = "calibrated_match_probability"
    UNCALIBRATED_SIMILARITY = "uncalibrated_similarity"


@unique
class CandidateRegistrationAction(StrEnum):
    REGISTER_IMMEDIATELY = "register_immediately"


class CameraRoutingInput(ZoneSearchModel):
    camera_id: str = Field(min_length=1, max_length=100)
    zone_id: int = Field(gt=0)
    position: int = Field(ge=1, le=CAMERAS_PER_ZONE)
    available: bool = True
    recording_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    route_centrality: float = Field(default=0.5, ge=0.0, le=1.0)
    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    prior_detection_score: float = Field(default=0.0, ge=0.0, le=1.0)
    overlap_penalty: float = Field(default=0.0, ge=0.0, le=1.0)


class ZoneSearchPlanRequest(ZoneSearchModel):
    case_id: str = Field(min_length=1, max_length=100)
    search_from: datetime
    search_to: datetime
    zone_count: int = Field(
        default=JURISDICTION_ZONE_COUNT,
        ge=JURISDICTION_ZONE_COUNT,
        le=JURISDICTION_ZONE_COUNT,
    )
    cameras_per_zone: int = Field(
        default=CAMERAS_PER_ZONE,
        ge=CAMERAS_PER_ZONE,
        le=CAMERAS_PER_ZONE,
    )
    expected_zone_id: int | None = Field(default=None, gt=0)
    expected_zone_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    live_search_enabled: bool = True
    cameras: tuple[CameraRoutingInput, ...] = Field(min_length=1, max_length=1_600)

    @model_validator(mode="after")
    def validate_search_topology(self) -> Self:
        if self.search_from.utcoffset() is None or self.search_to.utcoffset() is None:
            message = "search timestamps must include a timezone"
            raise ValueError(message)
        if self.search_from > self.search_to:
            message = "searchFrom must not be later than searchTo"
            raise ValueError(message)
        if self.expected_zone_id is None and self.expected_zone_confidence > 0.0:
            message = "expectedZoneConfidence requires expectedZoneId"
            raise ValueError(message)
        if self.expected_zone_id is not None:
            if self.expected_zone_id > self.zone_count:
                message = "expectedZoneId exceeds zoneCount"
                raise ValueError(message)
            if self.expected_zone_confidence <= 0.0:
                message = "expectedZoneId requires positive expectedZoneConfidence"
                raise ValueError(message)

        expected_camera_count = self.zone_count * self.cameras_per_zone
        if len(self.cameras) != expected_camera_count:
            message = "camera count does not match the declared topology"
            raise ValueError(message)
        camera_ids = {camera.camera_id for camera in self.cameras}
        if len(camera_ids) != len(self.cameras):
            message = "cameraId values must be unique"
            raise ValueError(message)
        for zone_id in range(1, self.zone_count + 1):
            zone_cameras = tuple(
                camera for camera in self.cameras if camera.zone_id == zone_id
            )
            if len(zone_cameras) != self.cameras_per_zone:
                message = f"zone {zone_id} must contain exactly {self.cameras_per_zone} cameras"
                raise ValueError(message)
            positions = {camera.position for camera in zone_cameras}
            if frozenset(positions) != CAMERA_POSITIONS:
                message = f"zone {zone_id} camera positions must be consecutive"
                raise ValueError(message)
            if not any(camera.available for camera in zone_cameras):
                message = f"zone {zone_id} has no available camera"
                raise ValueError(message)
        return self


class RoutingScoreBreakdown(ZoneSearchModel):
    recording_coverage: float
    health: float
    route_centrality: float
    freshness: float
    prior_detection: float
    representative_bonus: float
    overlap_penalty: float


class SelectedCamera(ZoneSearchModel):
    camera_id: str
    zone_id: int
    position: int
    selection_score: float = Field(ge=0.0, le=1.0)
    routing_weight: float = Field(ge=0.0, le=1.0)
    zone_priority: float = Field(ge=0.0, le=1.0)
    score_breakdown: RoutingScoreBreakdown


class ZoneSearchPlanResponse(ZoneSearchModel):
    schema_version: str = ZONE_SEARCH_SCHEMA_VERSION
    case_id: str
    analysis_mode: AnalysisMode
    segment_order: SegmentOrder
    selected_cameras: tuple[SelectedCamera, ...]
    continue_after_candidate: bool = True


class ZoneCameraTarget(ZoneSearchModel):
    camera_id: str = Field(min_length=1, max_length=100)
    zone_id: int = Field(gt=0)
    position: int = Field(ge=1, le=CAMERAS_PER_ZONE)


def _validate_zone_cameras(
    zone_cameras: tuple[ZoneCameraTarget, ...],
    expected_zone_id: int,
    candidate_camera_id: str,
    candidate_position: int | None = None,
) -> None:
    camera_ids = {camera.camera_id for camera in zone_cameras}
    positions = {camera.position for camera in zone_cameras}
    if len(camera_ids) != len(zone_cameras):
        message = "zone camera IDs must be unique"
        raise ValueError(message)
    if frozenset(positions) != CAMERA_POSITIONS:
        message = f"zone camera positions must be 1 through {CAMERAS_PER_ZONE}"
        raise ValueError(message)
    if any(camera.zone_id != expected_zone_id for camera in zone_cameras):
        message = "every zone camera must belong to the expected zone"
        raise ValueError(message)
    candidate_camera = next(
        (camera for camera in zone_cameras if camera.camera_id == candidate_camera_id),
        None,
    )
    if candidate_camera is None:
        message = "candidate camera must belong to zoneCameras"
        raise ValueError(message)
    if candidate_position is not None and candidate_camera.position != candidate_position:
        message = "cameraPosition does not match candidate camera topology"
        raise ValueError(message)


class CandidateEventRequest(ZoneSearchModel):
    case_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=100)
    camera_id: str = Field(min_length=1, max_length=100)
    zone_id: int = Field(gt=0)
    camera_position: int = Field(ge=1, le=CAMERAS_PER_ZONE)
    zone_cameras: tuple[ZoneCameraTarget, ...] = Field(
        min_length=CAMERAS_PER_ZONE,
        max_length=CAMERAS_PER_ZONE,
    )
    model_similarity: float = Field(ge=0.0, le=1.0)
    calibrated_match_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_camera_topology(self) -> Self:
        _validate_zone_cameras(
            self.zone_cameras,
            self.zone_id,
            self.camera_id,
            self.camera_position,
        )
        return self


class CandidateEventDirective(ZoneSearchModel):
    schema_version: str = ZONE_SEARCH_SCHEMA_VERSION
    case_id: str
    candidate_id: str
    registration_action: CandidateRegistrationAction
    registration_completed: bool = False
    event_key: str
    operator_review_required: bool = True
    continue_recording_analysis: bool = True
    display_score: float = Field(ge=0.0, le=1.0)
    score_kind: ScoreKind


class OperatorDecisionRequest(ZoneSearchModel):
    case_id: str = Field(min_length=1, max_length=100)
    candidate_id: str = Field(min_length=1, max_length=100)
    candidate_camera_id: str = Field(min_length=1, max_length=100)
    candidate_zone_id: int = Field(gt=0)
    decision: OperatorDecision
    decision_at: datetime
    routing_revision: int = Field(ge=1)
    active_routing_revision: int = Field(ge=0)
    live_search_enabled: bool = True
    zone_cameras: tuple[ZoneCameraTarget, ...] = Field(
        min_length=CAMERAS_PER_ZONE,
        max_length=CAMERAS_PER_ZONE,
    )
    model_similarity: float = Field(ge=0.0, le=1.0)
    calibrated_match_probability: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_zone_cameras(self) -> Self:
        if self.decision_at.utcoffset() is None:
            message = "decisionAt must include a timezone"
            raise ValueError(message)
        _validate_zone_cameras(
            self.zone_cameras,
            self.candidate_zone_id,
            self.candidate_camera_id,
        )
        return self


class OperatorDecisionDirective(ZoneSearchModel):
    schema_version: str = ZONE_SEARCH_SCHEMA_VERSION
    case_id: str
    candidate_id: str
    action: JetsonAction
    decision_at: datetime
    routing_revision: int = Field(ge=1)
    command_key: str
    target_zone_id: int | None = Field(default=None, gt=0)
    replace_active_zone: bool = False
    target_camera_ids: tuple[str, ...]
    continue_recording_analysis: bool = True
    display_score: float = Field(ge=0.0, le=1.0)
    score_kind: ScoreKind

