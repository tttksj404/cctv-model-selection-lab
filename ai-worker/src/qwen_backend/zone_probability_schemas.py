from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum, unique
from typing import Annotated, Self
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from .zone_search_schemas import ZONE_SEARCH_SCHEMA_VERSION, ZoneSearchModel
from .zone_topology import (
    CAMERA_POSITIONS,
    CAMERAS_PER_ZONE,
    JURISDICTION_ZONE_COUNT,
)

SHA256_PATTERN = r"^[0-9a-f]{64}$"
MAX_CONTINUATION_DEDUP_ENTRIES = 10_000
IdentifierDigest = Annotated[str, Field(pattern=SHA256_PATTERN)]


def sha256_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


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
class CandidatePoolStatus(StrEnum):
    CANDIDATE_FOUND = "candidate_found"
    REVIEW_REQUIRED = "review_required"
    SEARCH_BROADLY = "search_broadly"


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
    correlation_group_id: str = Field(min_length=1, max_length=200)
    observation_group_id: str = Field(min_length=1, max_length=300)
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
    position: int = Field(ge=1, le=CAMERAS_PER_ZONE)
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


class EvidenceDeduplicationState(ZoneSearchModel):
    source_routing_revision: int = Field(ge=1)
    event_id_digests: tuple[IdentifierDigest, ...] = Field(
        default=(), max_length=MAX_CONTINUATION_DEDUP_ENTRIES
    )
    correlation_group_digests: tuple[IdentifierDigest, ...] = Field(
        default=(), max_length=MAX_CONTINUATION_DEDUP_ENTRIES
    )
    observation_group_digests: tuple[IdentifierDigest, ...] = Field(
        default=(), max_length=MAX_CONTINUATION_DEDUP_ENTRIES
    )

    @model_validator(mode="after")
    def validate_unique_digests(self) -> Self:
        digest_groups = (
            self.event_id_digests,
            self.correlation_group_digests,
            self.observation_group_digests,
        )
        if any(len(values) != len(set(values)) for values in digest_groups):
            message = "continuation deduplication digests must be unique"
            raise ValueError(message)
        return self


class ZoneProbabilityRequest(ZoneSearchModel):
    case_id: str = Field(min_length=1, max_length=100)
    request_id: UUID = Field(default_factory=uuid4)
    issued_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    routing_revision: int = Field(ge=1)
    active_routing_revision: int = Field(default=0, ge=0)
    zone_count: int = Field(
        default=JURISDICTION_ZONE_COUNT,
        ge=JURISDICTION_ZONE_COUNT,
        le=JURISDICTION_ZONE_COUNT,
    )
    candidate_prior_probability: float = Field(default=0.10, gt=0.0, lt=1.0)
    advance_motion: bool = True
    motion_elapsed_seconds: int = Field(default=300, ge=0, le=2_592_000)
    motion_step_seconds: int = Field(default=300, ge=1, le=86_400)
    previous_zone_posterior: tuple[ZoneBeliefInput, ...] = ()
    previous_outside_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    previous_unknown_probability: float = Field(default=0.10, ge=0.0, le=1.0)
    previous_deduplication_state: EvidenceDeduplicationState | None = None
    topology_edges: tuple[ZoneEdge, ...] = Field(default=(), max_length=400)
    evidence_signature: str | None = Field(default=None, pattern=SHA256_PATTERN)
    evidence: tuple[CandidateProbabilityEvidence, ...] = Field(max_length=2_000)
    cameras: tuple[CameraObservation, ...] = Field(
        min_length=CAMERAS_PER_ZONE,
        max_length=400,
    )

    @model_validator(mode="after")
    def validate_topology_and_belief(self) -> Self:
        if self.issued_at.utcoffset() is None:
            message = "issuedAt must include a timezone"
            raise ValueError(message)
        if self.routing_revision <= self.active_routing_revision:
            message = "routingRevision must be newer than activeRoutingRevision"
            raise ValueError(message)
        if self.motion_elapsed_seconds > self.motion_step_seconds * 1_000:
            message = "motion transition steps cannot exceed 1000"
            raise ValueError(message)
        expected_camera_count = self.zone_count * CAMERAS_PER_ZONE
        if len(self.cameras) != expected_camera_count:
            message = f"each zone must contain exactly {CAMERAS_PER_ZONE} cameras"
            raise ValueError(message)
        camera_ids = {camera.camera_id for camera in self.cameras}
        if len(camera_ids) != len(self.cameras):
            message = "cameraId values must be unique"
            raise ValueError(message)
        camera_by_id = {camera.camera_id: camera for camera in self.cameras}
        event_ids: set[str] = set()
        observation_group_locations: dict[str, tuple[int, str]] = {}
        local_track_correlations: dict[tuple[str, str], str] = {}
        for zone_id in range(1, self.zone_count + 1):
            zone_cameras = tuple(camera for camera in self.cameras if camera.zone_id == zone_id)
            if frozenset(camera.position for camera in zone_cameras) != CAMERA_POSITIONS:
                message = (
                    f"zone {zone_id} camera positions must be 1 through "
                    f"{CAMERAS_PER_ZONE}"
                )
                raise ValueError(message)
            if not any(camera.available for camera in zone_cameras):
                message = f"zone {zone_id} has no available camera"
                raise ValueError(message)
        for evidence in self.evidence:
            if evidence.event_id in event_ids:
                message = "eventId values must be unique"
                raise ValueError(message)
            event_ids.add(evidence.event_id)
            camera = camera_by_id.get(evidence.camera_id)
            if camera is None or camera.zone_id != evidence.zone_id:
                message = "evidence cameraId and zoneId must match the camera topology"
                raise ValueError(message)
            location = (evidence.zone_id, evidence.camera_id)
            previous_location = observation_group_locations.setdefault(
                evidence.observation_group_id, location
            )
            if previous_location != location:
                message = "one observationGroupId cannot span multiple cameras or zones"
                raise ValueError(message)
            local_track_key = (evidence.camera_id, evidence.track_id)
            previous_correlation = local_track_correlations.setdefault(
                local_track_key, evidence.correlation_group_id
            )
            if previous_correlation != evidence.correlation_group_id:
                message = "the same cameraId and trackId must keep one correlationGroupId"
                raise ValueError(message)
        state = self.previous_deduplication_state
        if self.active_routing_revision > 0:
            if not self.previous_zone_posterior or state is None:
                message = (
                    "continuation requests require the previous posterior and "
                    "previousDeduplicationState"
                )
                raise ValueError(message)
            if state.source_routing_revision != self.active_routing_revision:
                message = (
                    "previousDeduplicationState sourceRoutingRevision must equal "
                    "activeRoutingRevision"
                )
                raise ValueError(message)
        elif state is not None:
            message = "previousDeduplicationState requires an activeRoutingRevision"
            raise ValueError(message)
        if state is not None:
            projected_digest_sets = (
                set(state.event_id_digests)
                | {sha256_identifier(item.event_id) for item in self.evidence},
                set(state.correlation_group_digests)
                | {sha256_identifier(item.correlation_group_id) for item in self.evidence},
                set(state.observation_group_digests)
                | {sha256_identifier(item.observation_group_id) for item in self.evidence},
            )
            if any(
                len(values) > MAX_CONTINUATION_DEDUP_ENTRIES
                for values in projected_digest_sets
            ):
                message = "continuation deduplication state exceeds its safe capacity"
                raise ValueError(message)
        for edge in self.topology_edges:
            if edge.source_zone_id > self.zone_count or edge.target_zone_id > self.zone_count:
                message = "topology edge exceeds zoneCount"
                raise ValueError(message)
            if edge.source_zone_id == edge.target_zone_id:
                message = "topology edges cannot be self-loops"
                raise ValueError(message)
        prior_non_zone = (
            self.previous_outside_probability + self.previous_unknown_probability
        )
        if self.previous_zone_posterior:
            if len(self.previous_zone_posterior) != self.zone_count:
                message = "previousZonePosterior must contain every zone exactly once"
                raise ValueError(message)
            zone_ids = {item.zone_id for item in self.previous_zone_posterior}
            if (
                len(zone_ids) != len(self.previous_zone_posterior)
                or zone_ids != set(range(1, self.zone_count + 1))
            ):
                message = "previousZonePosterior must contain every zone exactly once"
                raise ValueError(message)
            total = sum(item.probability for item in self.previous_zone_posterior) + prior_non_zone
            if abs(total - 1.0) > 1e-6:
                message = "previous posterior probabilities must sum to one"
                raise ValueError(message)
        elif prior_non_zone >= 1.0:
            message = "outside and unknown priors must leave positive probability for zones"
            raise ValueError(message)
        return self


class CandidateAssessment(ZoneSearchModel):
    event_id: str
    track_id: str
    zone_id: int
    camera_id: str
    observation_group_id: str
    observed_at: datetime
    match_probability: float = Field(ge=0.0, le=1.0)
    likelihood_ratio: float = Field(gt=0.0)
    priority_band: CandidatePriorityBand
    signal_count: int = Field(ge=1)
    used_for_zone_update: bool


class ZonePosteriorItem(ZoneSearchModel):
    zone_id: int
    probability: float = Field(ge=0.0, le=1.0)


class ZoneCandidateSummary(ZoneSearchModel):
    zone_id: int
    candidate_count: int = Field(ge=0)
    top_candidate_event_id: str | None
    top_candidate_match_probability: float | None = Field(default=None, ge=0.0, le=1.0)
    zone_presence_probability: float = Field(ge=0.0, le=1.0)


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
    candidate_pool_status: CandidatePoolStatus
    deduplication_state: EvidenceDeduplicationState
    suppressed_replayed_event_ids: tuple[str, ...]
    suppressed_correlated_event_ids: tuple[str, ...]
    suppressed_alternative_event_ids: tuple[str, ...]
    zone_posterior: tuple[ZonePosteriorItem, ...]
    zone_candidate_summaries: tuple[ZoneCandidateSummary, ...]
    most_likely_zone_id: int
    most_likely_zone_probability: float = Field(ge=0.0, le=1.0)
    posterior_entropy: float = Field(ge=0.0)
    outside_probability: float = Field(ge=0.0, le=1.0)
    unknown_probability: float = Field(ge=0.0, le=1.0)
    ranked_cameras: tuple[RankedCamera, ...]
    next_camera_id: str | None
    camera_selection_policy: str = "posterior_weighted_coverage_with_eig_tiebreak"
    operator_review_required: bool = True
    auto_match_allowed: bool = False

    @model_validator(mode="after")
    def validate_probability_distribution(self) -> Self:
        if not self.operator_review_required or self.auto_match_allowed:
            message = "operator review must remain required and automatic match disabled"
            raise ValueError(message)
        if self.deduplication_state.source_routing_revision != self.routing_revision:
            message = "deduplication state must be issued for the response routingRevision"
            raise ValueError(message)
        zone_ids = [item.zone_id for item in self.zone_posterior]
        if len(zone_ids) != len(set(zone_ids)):
            message = "zonePosterior zoneId values must be unique"
            raise ValueError(message)
        total = (
            sum(item.probability for item in self.zone_posterior)
            + self.outside_probability
            + self.unknown_probability
        )
        if abs(total - 1.0) > 1e-9:
            message = "response posterior probabilities must sum to one"
            raise ValueError(message)
        return self

