from __future__ import annotations

# pyright: reportPrivateUsage=false
import scripts.benchmark_zone_probability_policy as benchmark
from qwen_backend.zone_probability_schemas import (
    CandidatePoolStatus,
    EvidenceDeduplicationState,
    RankedCamera,
    ZonePosteriorItem,
    ZoneProbabilityResponse,
)


def _response(
    zone_probabilities: tuple[float, float, float, float],
    ranked_cameras: tuple[RankedCamera, ...],
) -> ZoneProbabilityResponse:
    remaining = 1.0 - sum(zone_probabilities)
    most_likely_zone_id = max(range(1, 5), key=lambda zone_id: zone_probabilities[zone_id - 1])
    return ZoneProbabilityResponse(
        case_id="candidate-policy-test",
        routing_revision=1,
        candidate_assessments=(),
        candidate_pool_status=CandidatePoolStatus.SEARCH_BROADLY,
        deduplication_state=EvidenceDeduplicationState(source_routing_revision=1),
        suppressed_replayed_event_ids=(),
        suppressed_correlated_event_ids=(),
        suppressed_alternative_event_ids=(),
        zone_posterior=tuple(
            ZonePosteriorItem(zone_id=zone_id, probability=probability)
            for zone_id, probability in enumerate(zone_probabilities, start=1)
        ),
        zone_candidate_summaries=(),
        most_likely_zone_id=most_likely_zone_id,
        most_likely_zone_probability=zone_probabilities[most_likely_zone_id - 1],
        posterior_entropy=0.0,
        outside_probability=remaining / 2.0,
        unknown_probability=remaining / 2.0,
        ranked_cameras=ranked_cameras,
        next_camera_id=None,
    )


def _camera(
    camera_id: str,
    zone_id: int,
    *,
    recording_coverage: float,
    health_score: float,
    sensitivity: float = 0.84,
    false_positive_rate: float = 0.09,
) -> benchmark.ReplayCamera:
    return benchmark.ReplayCamera(
        camera_id=camera_id,
        zone_id=zone_id,
        position=1,
        available=True,
        recording_coverage=recording_coverage,
        health_score=health_score,
        freshness_score=1.0,
        route_centrality=1.0,
        sensitivity=sensitivity,
        false_positive_rate=false_positive_rate,
        operating_point_id="test",
        operating_point_sha256="0" * 64,
    )


def _ranked_camera(
    camera_id: str,
    zone_id: int,
    *,
    zone_probability: float,
    utility: float,
    expected_information_gain: float,
    operational_factor: float,
) -> RankedCamera:
    return RankedCamera(
        camera_id=camera_id,
        zone_id=zone_id,
        position=1,
        zone_probability=zone_probability,
        expected_information_gain=expected_information_gain,
        operational_factor=operational_factor,
        utility=utility,
    )


def test_expected_detection_prefers_true_hit_probability_over_runtime_noise() -> None:
    cameras = (
        _camera("1-1", 1, recording_coverage=0.25, health_score=0.80),
        _camera("2-1", 2, recording_coverage=0.90, health_score=1.00),
    )
    response = _response(
        (0.55, 0.35, 0.025, 0.025),
        (
            _ranked_camera(
                "1-1",
                1,
                zone_probability=0.55,
                utility=0.60,
                expected_information_gain=0.10,
                operational_factor=0.90,
            ),
            _ranked_camera(
                "2-1",
                2,
                zone_probability=0.35,
                utility=0.40,
                expected_information_gain=0.20,
                operational_factor=0.80,
            ),
        ),
    )

    selected = benchmark._choose_camera("expected_detection", response, cameras, frozenset())

    assert selected is not None
    assert selected.camera_id == "2-1"


def test_risk_adjusted_detection_penalizes_false_hit_exposure() -> None:
    cameras = (
        _camera("1-1", 1, recording_coverage=1.00, health_score=1.00),
        _camera("2-1", 2, recording_coverage=0.50, health_score=1.00),
    )
    response = _response(
        (0.25, 0.40, 0.10, 0.10),
        (
            _ranked_camera(
                "1-1",
                1,
                zone_probability=0.25,
                utility=0.25,
                expected_information_gain=0.30,
                operational_factor=1.00,
            ),
            _ranked_camera(
                "2-1",
                2,
                zone_probability=0.40,
                utility=0.20,
                expected_information_gain=0.20,
                operational_factor=0.50,
            ),
        ),
    )

    unpenalized = benchmark._choose_camera("expected_detection", response, cameras, frozenset())
    risk_adjusted = benchmark._choose_camera(
        "risk_adjusted_detection_2_0", response, cameras, frozenset()
    )

    assert unpenalized is not None
    assert unpenalized.camera_id == "1-1"
    assert risk_adjusted is not None
    assert risk_adjusted.camera_id == "2-1"


def test_bayes_objectives_choose_cameras_for_their_declared_metric() -> None:
    cameras = (
        _camera("1-1", 1, recording_coverage=1.00, health_score=1.00),
        _camera("2-1", 2, recording_coverage=1.00, health_score=1.00),
    )
    response = _response(
        (0.45, 0.35, 0.05, 0.05),
        (
            _ranked_camera(
                "1-1",
                1,
                zone_probability=0.45,
                utility=0.45,
                expected_information_gain=0.10,
                operational_factor=1.00,
            ),
            _ranked_camera(
                "2-1",
                2,
                zone_probability=0.35,
                utility=0.35,
                expected_information_gain=0.20,
                operational_factor=1.00,
            ),
        ),
    )

    accuracy_focused = benchmark._choose_camera(
        "expected_bayes_accuracy", response, cameras, frozenset()
    )
    resolution_focused = benchmark._choose_camera(
        "expected_resolution_0_55", response, cameras, frozenset()
    )

    assert accuracy_focused is not None
    assert accuracy_focused.camera_id == "2-1"
    assert resolution_focused is not None
    assert resolution_focused.camera_id == "1-1"
