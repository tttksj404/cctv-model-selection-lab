from __future__ import annotations

from datetime import UTC, datetime

from qwen_backend.probability_provenance import sign_probability_request
from qwen_backend.zone_probability_schemas import (
    CameraObservation,
    CameraObservationStatus,
    CandidateProbabilityEvidence,
    ProbabilitySignal,
    ProbabilitySignalKind,
    ZoneProbabilityRequest,
)

MODEL_HASH = "81555144f412d46182d9cc8a0a01334f470a3484ce2fede88af9a5779d2a05a7"
EVIDENCE_HASH = "2ae983f7d3d124c87f48063c6f00fd313e96e14d8db1f4d04f0d3bb28e342c6c"
MANIFEST_HASH = "86b8f48bd4ad2e8b28ffbece11ac61796ce0653d636170f947c044bbdd4b0d6d"
TEST_SIGNING_KEY = "test-only-zone-probability-signing-key-2026"


def cameras(
    *,
    zone_one_observation: CameraObservationStatus = CameraObservationStatus.NOT_SCANNED,
) -> tuple[CameraObservation, ...]:
    return tuple(
        CameraObservation(
            camera_id=f"{zone_id}-{position}",
            zone_id=zone_id,
            position=position,
            available=True,
            recording_coverage=1.0,
            health_score=1.0,
            freshness_score=1.0,
            route_centrality=0.7 if position == 1 else 0.5,
            sensitivity=0.84,
            false_positive_rate=0.09,
            operating_point_id="prid2011-conservative-wilson-v1",
            operating_point_sha256=EVIDENCE_HASH,
            validation_sample_count=57,
            observation=(
                zone_one_observation
                if zone_id == 1 and position == 1
                else CameraObservationStatus.NOT_SCANNED
            ),
        )
        for zone_id in range(1, 5)
        for position in range(1, 5)
    )


def evidence(
    *,
    event_id: str = "event-1",
    track_id: str = "track-1",
    correlation_group_id: str = "global-track-1",
    observation_group_id: str | None = None,
    zone_id: int = 3,
    probability: float = 0.92,
    quality: float = 1.0,
) -> CandidateProbabilityEvidence:
    return CandidateProbabilityEvidence(
        event_id=event_id,
        zone_id=zone_id,
        camera_id=f"{zone_id}-1",
        track_id=track_id,
        correlation_group_id=correlation_group_id,
        observation_group_id=(
            observation_group_id or f"recording-31:camera-{zone_id}-1:segment-1"
        ),
        observed_at=datetime(2026, 8, 1, 3, 0, tzinfo=UTC),
        track_quality=quality,
        signals=(
            ProbabilitySignal(
                signal_kind=ProbabilitySignalKind.REID,
                probability=probability,
                calibration_base_rate=0.10,
                reliability=1.0,
                model_id="solider-swin-b-msmt17",
                model_sha256=MODEL_HASH,
                calibrator_id="prid2011-open-set-v3-proxy-lr-v1",
                calibrator_sha256=EVIDENCE_HASH,
                calibration_manifest_sha256=MANIFEST_HASH,
                calibration_sample_count=57,
            ),
        ),
    )


def request(
    *,
    evidence_items: tuple[CandidateProbabilityEvidence, ...] = (),
    camera_items: tuple[CameraObservation, ...] | None = None,
) -> ZoneProbabilityRequest:
    unsigned_request = ZoneProbabilityRequest(
        case_id="case-77",
        routing_revision=3,
        zone_count=4,
        candidate_prior_probability=0.10,
        evidence=evidence_items,
        cameras=camera_items or cameras(),
    )
    return unsigned_request.model_copy(
        update={
            "evidence_signature": sign_probability_request(
                unsigned_request,
                TEST_SIGNING_KEY,
            )
        }
    )
