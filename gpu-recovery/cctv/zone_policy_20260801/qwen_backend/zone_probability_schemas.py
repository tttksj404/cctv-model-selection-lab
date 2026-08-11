from __future__ import annotations

from datetime import datetime
from enum import StrEnum, unique
from typing import Self

from pydantic import Field, model_validator

from .zone_search_schemas import ZONE_SEARCH_SCHEMA_VERSION, ZoneSearchModel

SHA256_PATTERN = r"^[0-9a-f]{64}$"


@unique
class ProbabilitySignalKind(StrEnum):
    REID = "reid"
    SEMANTIC = "semantic"
    ATTRIBUTE = "attribute"


@unique
class CandidatePriorityBand(StrEnum):
    HIGH_PRIORITY = "high_priority"
    REVIEW = "review"
    LOW_PRIORITY = "low_priority"


@unique
class CameraObservationStatus(StrEnum):
    NOT_SCANNED = "not_scanned"
    MATCH = "match"
    NO_MATCH = "no_match"


class ProbabilitySignal(ZoneSearchModel):
    signal_kind: ProbabilitySignalKind
    probability: float = Field(gt=0.0, lt=1.0)
    calibration_base_rate: float = Field(gt=0.0, lt=1.0)
    reliability: float = Field(default=1.0, gt=0.0, le=1.0)
    model_id: str = Field(min_length=1, max_length=200)
    model_sha256: str = Field(pattern=SHA256_PATTERN)
    calibrator_id: str = Field(min_length=1, max_length=200)
    calibrator_sha256: str = Field(pattern=SHA256_PATTERN)
    calibration_manifest_sha256: str = Field(pattern=SHA256_PATTERN)
    calibration_sample_count: int = Field(ge=20)


class CandidateProbabilityEvidence(ZoneSearchModel):
    event_id: str = Field(min_length=1, max_length=200)
    zone_id: int = Field(gt=0)
    camera_id: str = Field(min_length=1, max_length=100)
    track_id: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    track_quality: float = Field(default=1.0, gt=0.0, le=1.0)
    signals: tuple[ProbabilitySignal, ...] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def validate_evidence(self) -> Self:
        if self.observed_at.utcoffset() is None:
            message = "observedAt must include a timezone"
            raise ValueError(message)
        kinds = {signal.signal_kind for signal in self.signals}
        if len(kinds) != len(self.signals):
            message = "signalKind values must be unique within one evidence event"
            raise ValueError(message)
        return self


class CameraObservation(ZoneSearchModel):
    camera_id: str = Field(min_length=1, max_length=100)
    zone_id: int = Field(gt=0)
    position: int = Field(ge=1, le=4)
    available: bool = True
    recording_coverage: float = Field(default=1.0, ge=0.0, le=1.0)
    health_score: float = Field(default=1.0, ge=0.0, le=1.0)
    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    route_centrality: float = Field(default=0.5, ge=0.0, le=1.0)
    sensitivity: float = Field(gt=0.0, lt=1.0)
    false_positive_rate: float = Field(gt=0.0, lt=1.0)
    operating_point_id: str = Field(min_length=1, max_length=200)
    operating_point_sha256: str = Field(pattern=SHA256_PATTERN)
    validation_sample_count: int = Field(ge=20)
    already_scanned: bool = False
    observation: CameraObservationStatus = CameraObservationStatus.NOT_SCANNED


class ZoneBeliefInput(ZoneSearchModel):
    zone_id: int = Field(gt=0)
    probability: float = Field(ge=0.0, le=1.0)


class ZoneEdge(ZoneSearchModel):
    source_zone_id: int = Field(gt=0)
    target_zone_id: int = Field(gt=0)


class ZoneProbabilityRequest(ZoneSearchModel):
    case_id: str = Field(min_length=1, max_length=100)
    routing_revision: int = Field(ge=1)
    zone_count: int = Field(default=4, ge=1, le=100)
    candidate_prior_probability: float = Field(default=0.10, gt=0.0, lt=1.0)
    advance_motion: bool = True
    previous_zone_posterior: tuple[ZoneBeliefInput, ...] = ()
    previous_outside_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    previous_unknown_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    topology_edges: tuple[ZoneEdge, ...] = ()
    evidence: tuple[CandidateProbabilityEvidence, ...] = Field(max_length=10_000)
    cameras: tuple[CameraObservation, ...] = Field(min_length=4, max_length=400)

    @model_validator(mode="after")
    def validate_topology_and_belief(self) -> Self:
        expected_camera_count = self.zone_count * 4
        if len(self.cameras) != expected_camera_count:
            message = "each zone must contain exactly four cameras"
            raise ValueError(message)
        camera_ids = {camera.camera_id for camera in self.cameras}
        if len(camera_ids) != len(self.cameras):
            message = "cameraId values must be unique"
            raise ValueError(message)
        camera_by_id = {camera.camera_id: camera for camera in self.cameras}
        for zone_id in range(1, self.zone_count + 1):
            zone_cameras = tuple(camera for camera in self.cameras if camera.zone_id == zone_id)
            if {camera.position for camera in zone_cameras} != {1, 2, 3, 4}:
                message = f"zone {zone_id} camera positions must be 1 through 4"
                raise ValueError(message)
            if not any(camera.available for camera in zone_cameras):
                message = f"zone {zone_id} has no available camera"
                raise ValueError(message)
        for evidence in self.evidence:
            camera = camera_by_id.get(evidence.camera_id)
            if camera is None or camera.zone_id != evidence.zone_id:
                message = "evidence cameraId and zoneId must match the camera topology"
                raise ValueError(message)
        for edge in self.topology_edges:
            if edge.source_zone_id > self.zone_count or edge.target_zone_id > self.zone_count:
                message = "topology edge exceeds zoneCount"
                raise ValueError(message)
            if edge.source_zone_id == edge.target_zone_id:
                message = "topology edges cannot be self-loops"
                raise ValueError(message)
        if self.previous_zone_posterior:
            zone_ids = {item.zone_id for item in self.previous_zone_posterior}
            if zone_ids != set(range(1, self.zone_count + 1)):
                message = "previousZonePosterior must contain every zone exactly once"
                raise ValueError(message)
            total = (
                sum(item.probability for item in self.previous_zone_posterior)
                + self.previous_outside_probability
                + self.previous_unknown_probability
            )
            if abs(total - 1.0) > 1e-6:
                message = "previous posterior probabilities must sum to one"
                raise ValueError(message)
        return self


class CandidateAssessment(ZoneSearchModel):
    event_id: str
    track_id: str
    zone_id: int
    match_probability: float = Field(ge=0.0, le=1.0)
    likelihood_ratio: float = Field(gt=0.0)
    priority_band: CandidatePriorityBand
    signal_count: int = Field(ge=1)


class ZonePosteriorItem(ZoneSearchModel):
    zone_id: int
    probability: float = Field(ge=0.0, le=1.0)


class RankedCamera(ZoneSearchModel):
    camera_id: str
    zone_id: int
    position: int
    zone_probability: float = Field(ge=0.0, le=1.0)
    expected_information_gain: float = Field(ge=0.0)
    operational_factor: float = Field(ge=0.0, le=1.0)
    utility: float = Field(ge=0.0)


class ZoneProbabilityResponse(ZoneSearchModel):
    schema_version: str = ZONE_SEARCH_SCHEMA_VERSION
    case_id: str
    routing_revision: int
    candidate_assessments: tuple[CandidateAssessment, ...]
    suppressed_correlated_event_ids: tuple[str, ...]
    zone_posterior: tuple[ZonePosteriorItem, ...]
    outside_probability: float = Field(ge=0.0, le=1.0)
    unknown_probability: float = Field(ge=0.0, le=1.0)
    ranked_cameras: tuple[RankedCamera, ...]
    next_camera_id: str | None
    camera_selection_policy: str = "posterior_weighted_coverage_with_eig_tiebreak"
    operator_review_required: bool = True
    auto_match_allowed: bool = False
