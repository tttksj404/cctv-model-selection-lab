from __future__ import annotations

import argparse
import json
import os
from datetime import UTC, datetime

from qwen_backend.config import DEFAULT_PROBABILITY_TRUST_REGISTRY
from qwen_backend.probability_provenance import (
    load_probability_trust_registry,
    sign_probability_request,
)
from qwen_backend.zone_probability_schemas import (
    CameraObservation,
    CandidateProbabilityEvidence,
    ProbabilitySignal,
    ZoneProbabilityRequest,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print one trusted development request for the zone-probability API"
    )
    parser.add_argument("--case-id", default="case-demo-1")
    parser.add_argument("--probability", type=float, default=0.82)
    parser.add_argument("--zone-id", type=int, choices=range(1, 5), default=1)
    args = parser.parse_args()
    signing_key = os.environ.get("QWEN_PROBABILITY_EVIDENCE_SIGNING_KEY")
    if signing_key is None:
        parser.error("QWEN_PROBABILITY_EVIDENCE_SIGNING_KEY must be configured")

    registry = load_probability_trust_registry(DEFAULT_PROBABILITY_TRUST_REGISTRY)
    signal_profile = registry.signals[0]
    camera_profile = registry.camera_operating_points[0]
    evidence = CandidateProbabilityEvidence(
        event_id="event-demo-1",
        zone_id=args.zone_id,
        camera_id=f"{args.zone_id}-1",
        track_id="local-track-7",
        correlation_group_id="global-track-demo-7",
        observation_group_id=f"recording-demo:camera-{args.zone_id}-1:segment-1",
        observed_at=datetime(2026, 8, 1, 3, 0, tzinfo=UTC),
        track_quality=0.90,
        signals=(
            ProbabilitySignal(
                signal_kind=signal_profile.signal_kind,
                probability=args.probability,
                calibration_base_rate=signal_profile.calibration_base_rate,
                reliability=signal_profile.maximum_reliability,
                model_id=signal_profile.model_id,
                model_sha256=signal_profile.model_sha256,
                calibrator_id=signal_profile.calibrator_id,
                calibrator_sha256=signal_profile.calibrator_sha256,
                calibration_manifest_sha256=signal_profile.calibration_manifest_sha256,
                calibration_sample_count=signal_profile.minimum_sample_count,
            ),
        ),
    )
    cameras = tuple(
        CameraObservation(
            camera_id=f"{zone_id}-{position}",
            zone_id=zone_id,
            position=position,
            recording_coverage=1.0,
            health_score=1.0,
            freshness_score=1.0,
            route_centrality=0.7 if position == 1 else 0.5,
            sensitivity=camera_profile.sensitivity,
            false_positive_rate=camera_profile.false_positive_rate,
            operating_point_id=camera_profile.operating_point_id,
            operating_point_sha256=camera_profile.operating_point_sha256,
            validation_sample_count=camera_profile.minimum_sample_count,
        )
        for zone_id in range(1, 5)
        for position in range(1, 5)
    )
    unsigned_request = ZoneProbabilityRequest(
        case_id=args.case_id,
        routing_revision=1,
        active_routing_revision=0,
        motion_elapsed_seconds=300,
        motion_step_seconds=300,
        evidence=(evidence,),
        cameras=cameras,
    )
    request = unsigned_request.model_copy(
        update={
            "evidence_signature": sign_probability_request(
                unsigned_request,
                signing_key,
            )
        }
    )
    print(json.dumps(request.model_dump(mode="json", by_alias=True), separators=(",", ":")))


if __name__ == "__main__":
    main()

