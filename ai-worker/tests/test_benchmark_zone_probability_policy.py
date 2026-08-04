from __future__ import annotations

# pyright: reportPrivateUsage=false
import json
import random
from pathlib import Path

import pytest

import scripts.benchmark_zone_probability_policy as benchmark
from qwen_backend.zone_probability_schemas import (
    CandidatePoolStatus,
    EvidenceDeduplicationState,
    RankedCamera,
    ZonePosteriorItem,
    ZoneProbabilityRequest,
    ZoneProbabilityResponse,
)


def _response(
    zone_probabilities: tuple[float, float, float, float],
    ranked_cameras: tuple[RankedCamera, ...] = (),
) -> ZoneProbabilityResponse:
    remaining = 1.0 - sum(zone_probabilities)
    most_likely_zone_id = max(range(1, 5), key=lambda zone_id: zone_probabilities[zone_id - 1])
    return ZoneProbabilityResponse(
        case_id="benchmark-test",
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


def test_final_scan_false_zone_activation_is_counted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    point = benchmark.OperatingPoint("test", 0.84, 0.09, 0.0)
    cameras = benchmark._cameras(random.Random(7), point)
    responses = iter(
        (
            _response((0.20, 0.20, 0.20, 0.20)),
            _response((0.04, 0.80, 0.03, 0.03)),
        )
    )
    monkeypatch.setattr(benchmark, "MAX_SCANS", 1)

    def fake_assess(_request: ZoneProbabilityRequest) -> ZoneProbabilityResponse:
        return next(responses)

    monkeypatch.setattr(benchmark, "assess_zone_probability", fake_assess)

    outcome = benchmark._run_episode(
        episode_id="final-scan-false-activation",
        cohort="sealed_test",
        scenario="currently_inside",
        point=point,
        policy="static_representative",
        target=1,
        cameras=cameras,
        evidence=(),
        prior=benchmark._prior(random.Random(9), "currently_inside", 1),
        observation_draws={camera.camera_id: 1.0 for camera in cameras},
    )

    assert outcome.false_zone_activation is True


def test_hybrid_policy_weight_changes_camera_choice() -> None:
    point = benchmark.OperatingPoint("test", 0.84, 0.09, 0.0)
    cameras = benchmark._cameras(random.Random(11), point)
    ranked = (
        RankedCamera(
            camera_id="1-1",
            zone_id=1,
            position=1,
            zone_probability=0.55,
            expected_information_gain=0.10,
            operational_factor=0.90,
            utility=0.60,
        ),
        RankedCamera(
            camera_id="2-1",
            zone_id=2,
            position=1,
            zone_probability=0.30,
            expected_information_gain=0.50,
            operational_factor=0.80,
            utility=0.40,
        ),
    )
    response = _response((0.55, 0.30, 0.05, 0.05), ranked)

    utility_focused = benchmark._choose_camera("hybrid_eig_0_25", response, cameras, frozenset())
    information_focused = benchmark._choose_camera(
        "hybrid_eig_0_75", response, cameras, frozenset()
    )

    assert utility_focused is not None
    assert utility_focused.camera_id == "1-1"
    assert information_focused is not None
    assert information_focused.camera_id == "2-1"


def test_paired_comparison_reports_zero_difference() -> None:
    baseline = [
        benchmark.EpisodeOutcome(
            cohort="sealed_test",
            episode_id=f"episode-{index}",
            scenario="location_uncertain",
            operating_point="test",
            policy="deployed_runtime",
            target_state=1,
            scans_to_resolution=3,
            resolved_within_budget=True,
            final_top1_correct=True,
            false_zone_activation=False,
        )
        for index in range(4)
    ]
    candidate = [
        benchmark.EpisodeOutcome(
            cohort=outcome.cohort,
            episode_id=outcome.episode_id,
            scenario=outcome.scenario,
            operating_point=outcome.operating_point,
            policy="hybrid_eig_0_25",
            target_state=outcome.target_state,
            scans_to_resolution=outcome.scans_to_resolution,
            resolved_within_budget=outcome.resolved_within_budget,
            final_top1_correct=outcome.final_top1_correct,
            false_zone_activation=outcome.false_zone_activation,
        )
        for outcome in baseline
    ]

    comparison = benchmark._paired_comparison(candidate, baseline)

    assert comparison["resolvedWithinBudgetRate"] == {
        "delta": 0.0,
        "delta95Lower": 0.0,
        "delta95Upper": 0.0,
        "includesZero": True,
    }


def test_paired_promotion_gate_requires_all_confidence_interval_bounds() -> None:
    comparison = {
        "resolvedWithinBudgetRate": {
            "delta95Lower": 0.001,
        },
        "falseZoneActivationRate": {
            "delta95Upper": 0.0,
        },
        "finalTop1Accuracy": {
            "delta95Lower": 0.0,
        },
    }

    assert benchmark._passes_paired_promotion_gate(comparison) is True

    comparison["resolvedWithinBudgetRate"]["delta95Lower"] = 0.0

    assert benchmark._passes_paired_promotion_gate(comparison) is False


def test_promotion_gate_uses_unrounded_false_activation_and_top1_bounds() -> None:
    comparison = {
        "resolvedWithinBudgetRate": benchmark._difference_interval([0.001] * 4),
        "falseZoneActivationRate": benchmark._difference_interval([0.0000001] * 4),
        "finalTop1Accuracy": benchmark._difference_interval([0.0] * 4),
    }

    assert benchmark._passes_paired_promotion_gate(comparison) is False

    comparison["falseZoneActivationRate"] = benchmark._difference_interval([0.0] * 4)
    comparison["finalTop1Accuracy"] = benchmark._difference_interval([-0.0000001] * 4)

    assert benchmark._passes_paired_promotion_gate(comparison) is False


def test_promotion_gate_rejects_boolean_confidence_bound() -> None:
    comparison = {
        "resolvedWithinBudgetRate": {
            "delta95Lower": True,
        },
        "falseZoneActivationRate": {
            "delta95Upper": 0.0,
        },
        "finalTop1Accuracy": {
            "delta95Lower": 0.0,
        },
    }

    assert benchmark._passes_paired_promotion_gate(comparison) is False


def test_unimplemented_candidate_never_becomes_generated_runtime_policy() -> None:
    runtime_policy = benchmark._runtime_policy_for(
        "hybrid_eig_0_25",
        proxy_material_improvement=True,
    )

    assert runtime_policy == (benchmark.RUNTIME_POLICY_IDS["deployed_runtime"])


def test_public_evidence_hash_is_stable_across_json_line_endings(
    tmp_path: Path,
) -> None:
    payload = {"status": "passed", "metrics": {"rank1": 0.85}}
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    lf_path = tmp_path / "lf.json"
    crlf_path = tmp_path / "crlf.json"
    lf_path.write_bytes((serialized + "\n").encode())
    crlf_path.write_bytes((serialized.replace("\n", "\r\n") + "\r\n").encode())

    assert benchmark._canonical_json_sha256(lf_path) == (
        benchmark._canonical_json_sha256(crlf_path)
    )


def test_public_reid_evidence_hashes_and_parses_one_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    evidence_path = (
        repository
        / "experiments/results/evidence/prid2011_solider_open_set_v3_revalidated_summary.json"
    )
    trusted = evidence_path.read_bytes()
    tampered_payload = json.loads(trusted)
    tampered_payload["testMetrics"]["known_rank1"] = 0.0
    tampered = json.dumps(tampered_payload, ensure_ascii=False).encode()
    original_read_bytes = Path.read_bytes
    reads = 0

    def alternating_read_bytes(path: Path) -> bytes:
        nonlocal reads
        if path.resolve() != evidence_path.resolve():
            return original_read_bytes(path)
        reads += 1
        return tampered if reads == 1 else trusted

    monkeypatch.setattr(Path, "read_bytes", alternating_read_bytes)

    with pytest.raises(benchmark.ReplayConfigurationError, match="digest is not trusted"):
        benchmark._public_reid_evidence(evidence_path)
    assert reads == 1


@pytest.mark.parametrize("test_metrics", [None, [], "invalid"])
def test_public_reid_evidence_rejects_malformed_test_metrics(
    tmp_path: Path,
    test_metrics: object,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = json.loads(
        (
            repository
            / "experiments/results/evidence/prid2011_solider_open_set_v3_revalidated_summary.json"
        ).read_bytes()
    )
    source["testMetrics"] = test_metrics
    malformed = tmp_path / "malformed-public-reid.json"
    malformed.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(benchmark.ReplayConfigurationError, match="schema is invalid"):
        benchmark._public_reid_evidence(malformed)
