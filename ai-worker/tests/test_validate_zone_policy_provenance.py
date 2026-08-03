from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import TypeAlias, cast

RESULT_SOURCE = "experiments/results/zone_policy_risk_replay_large_20260801.json"
JsonValue: TypeAlias = (
    bool | int | float | str | None | list["JsonValue"] | dict[str, "JsonValue"]
)


def _source_payload(repository: Path) -> dict[str, JsonValue]:
    return cast(
        dict[str, JsonValue],
        json.loads((repository / RESULT_SOURCE).read_text(encoding="utf-8")),
    )


def _run_validator(
    repository: Path,
    payload: dict[str, JsonValue],
    tmp_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, JsonValue]]:
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
    artifact = cast(
        dict[str, JsonValue],
        json.loads(output_path.read_text(encoding="utf-8")),
    )
    return completed, artifact


def test_validator_rejects_tampered_public_evidence_hash(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    public_evidence = cast(dict[str, JsonValue], payload["publicReidEvidence"])
    public_evidence["sha256"] = "0" * 64

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["public_reid_evidence_hash_matches"] is False
    assert artifact["passed"] is False


def test_validator_rejects_tampered_public_evidence_metrics(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    public_evidence = cast(dict[str, JsonValue], payload["publicReidEvidence"])
    public_evidence["knownQueries"] = True

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["public_reid_evidence_metrics_match"] is False
    assert artifact["passed"] is False


def test_validator_rejects_numeric_string_confidence_bounds(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    selected = cast(str, payload["selectedPolicy"])
    replay = cast(dict[str, JsonValue], payload["topologyReplayEvidence"])
    cohort = cast(dict[str, JsonValue], replay["sealedTestCohort"])
    comparisons = cast(
        dict[str, JsonValue], cohort["pairedComparisonsAgainstDeployed"]
    )
    selected_comparison = cast(dict[str, JsonValue], comparisons[selected])
    resolved = cast(
        dict[str, JsonValue], selected_comparison["resolvedWithinBudgetRate"]
    )
    resolved["delta95Lower"] = "0.001"

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["paired_interval_schema_valid"] is False
    assert artifact["passed"] is False


def test_validator_rejects_boolean_aggregate_metric(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    replay = cast(dict[str, JsonValue], payload["topologyReplayEvidence"])
    cohort = cast(dict[str, JsonValue], replay["sealedTestCohort"])
    aggregate = cast(dict[str, JsonValue], cohort["aggregateByPolicy"])
    deployed = cast(dict[str, JsonValue], aggregate["deployed_runtime"])
    deployed["resolvedWithinBudgetRate"] = True

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["aggregate_metric_schema_valid"] is False
    assert artifact["passed"] is False


def test_validator_rejects_claim_escalation(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    promotion = cast(dict[str, JsonValue], payload["promotionDecision"])
    replay = cast(dict[str, JsonValue], payload["topologyReplayEvidence"])
    promotion["cameraUtilityCausalImprovementConfirmed"] = True
    replay["projectCctvEvidence"] = True

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["causal_improvement_claim_blocked"] is False
    assert checks["topology_proxy_claim_enforced"] is False
    assert artifact["passed"] is False


def test_validator_rejects_nonfinite_json_number(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    payload["pairedEpisodeCount"] = float("inf")
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

    assert completed.returncode != 0
    assert not output_path.exists()
