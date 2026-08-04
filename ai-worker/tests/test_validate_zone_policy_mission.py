from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

RESULT_SOURCE = "experiments/results/zone_policy_risk_replay_large_20260801.json"


def test_validator_rejects_promotion_that_conflicts_with_paired_interval(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / RESULT_SOURCE
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["promotionDecision"]["proxyMaterialImprovementOverDeployedConfirmed"] = True
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(result_path),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert artifact["checks"]["promotion_decision_matches_paired_intervals"] is False
    assert artifact["passed"] is False


def test_validator_rejects_summary_forged_promotion_with_deployed_runtime_id(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / RESULT_SOURCE
    payload = json.loads(source.read_text(encoding="utf-8"))
    selected = payload["selectedPolicy"]
    for cohort_name in ("selectionCohort", "sealedTestCohort"):
        comparison = payload["topologyReplayEvidence"][cohort_name][
            "pairedComparisonsAgainstDeployed"
        ][selected]
        comparison["resolvedWithinBudgetRate"]["delta95Lower"] = 0.001
        comparison["falseZoneActivationRate"]["delta95Upper"] = 0.0
        comparison["finalTop1Accuracy"]["delta95Lower"] = 0.0
    payload["promotionDecision"]["selectionPairedIntervalPassed"] = True
    payload["promotionDecision"]["sealedTestPairedIntervalPassed"] = True
    payload["promotionDecision"]["proxyMaterialImprovementOverDeployedConfirmed"] = True
    payload["selectedRuntimePolicy"] = "lr_hmm_posterior_weighted_coverage_eig_tiebreak"
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(result_path),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert artifact["checks"]["summaries_recomputed_from_paired_evidence"] is False
    assert artifact["checks"]["selection_paired_interval_decision_matches"] is False
    assert artifact["checks"]["sealed_paired_interval_decision_matches"] is False
    assert artifact["checks"]["promotion_decision_matches_paired_intervals"] is False
    assert artifact["checks"]["runtime_policy_matches_promotion_decision"] is True
    assert artifact["checks"]["promoted_policy_has_runtime_implementation"] is True
    assert artifact["passed"] is False


def test_validator_rejects_summary_forged_unimplemented_runtime_policy(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / RESULT_SOURCE
    payload = json.loads(source.read_text(encoding="utf-8"))
    selected = payload["selectedPolicy"]
    for cohort_name in ("selectionCohort", "sealedTestCohort"):
        comparison = payload["topologyReplayEvidence"][cohort_name][
            "pairedComparisonsAgainstDeployed"
        ][selected]
        comparison["resolvedWithinBudgetRate"]["delta95Lower"] = 0.001
        comparison["falseZoneActivationRate"]["delta95Upper"] = 0.0
        comparison["finalTop1Accuracy"]["delta95Lower"] = 0.0
    payload["promotionDecision"]["selectionPairedIntervalPassed"] = True
    payload["promotionDecision"]["sealedTestPairedIntervalPassed"] = True
    payload["promotionDecision"]["proxyMaterialImprovementOverDeployedConfirmed"] = True
    payload["selectedRuntimePolicy"] = "lr_hmm_hybrid_eig_0_25"
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(result_path),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert artifact["checks"]["summaries_recomputed_from_paired_evidence"] is False
    assert artifact["checks"]["promotion_decision_matches_paired_intervals"] is False
    assert artifact["checks"]["runtime_policy_matches_promotion_decision"] is False
    assert artifact["checks"]["promoted_policy_has_runtime_implementation"] is True
    assert artifact["passed"] is False


def test_validator_rejects_candidate_that_only_passes_sealed_interval(
    tmp_path: Path,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / RESULT_SOURCE
    payload = json.loads(source.read_text(encoding="utf-8"))
    selected = payload["selectedPolicy"]
    selection_comparison = payload["topologyReplayEvidence"]["selectionCohort"][
        "pairedComparisonsAgainstDeployed"
    ][selected]
    selection_comparison["resolvedWithinBudgetRate"]["delta95Lower"] = 0.0
    sealed_comparison = payload["topologyReplayEvidence"]["sealedTestCohort"][
        "pairedComparisonsAgainstDeployed"
    ][selected]
    sealed_comparison["resolvedWithinBudgetRate"]["delta95Lower"] = 0.001
    sealed_comparison["falseZoneActivationRate"]["delta95Upper"] = 0.0
    sealed_comparison["finalTop1Accuracy"]["delta95Lower"] = 0.0
    payload["promotionDecision"]["selectionPairedIntervalPassed"] = True
    payload["promotionDecision"]["sealedTestPairedIntervalPassed"] = True
    payload["promotionDecision"]["proxyMaterialImprovementOverDeployedConfirmed"] = True
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(result_path),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert artifact["checks"]["selection_paired_interval_decision_matches"] is False
    assert artifact["checks"]["promotion_decision_matches_paired_intervals"] is False
    assert artifact["passed"] is False


def test_validator_rejects_boolean_confidence_bound(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = repository / RESULT_SOURCE
    payload = json.loads(source.read_text(encoding="utf-8"))
    selected = payload["selectedPolicy"]
    for cohort_name in ("selectionCohort", "sealedTestCohort"):
        comparison = payload["topologyReplayEvidence"][cohort_name][
            "pairedComparisonsAgainstDeployed"
        ][selected]
        comparison["resolvedWithinBudgetRate"]["delta95Lower"] = True
        comparison["falseZoneActivationRate"]["delta95Upper"] = 0.0
        comparison["finalTop1Accuracy"]["delta95Lower"] = 0.0
    payload["promotionDecision"]["selectionPairedIntervalPassed"] = True
    payload["promotionDecision"]["sealedTestPairedIntervalPassed"] = True
    payload["promotionDecision"]["proxyMaterialImprovementOverDeployedConfirmed"] = True
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(json.dumps(payload), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(result_path),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert completed.returncode == 1
    assert artifact["checks"]["selection_paired_interval_decision_matches"] is False
    assert artifact["passed"] is False
