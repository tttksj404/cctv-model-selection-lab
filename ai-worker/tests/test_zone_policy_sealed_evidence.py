from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import TypeAlias, cast

import pytest

import scripts.zone_policy_public_evidence as public_evidence_module
from scripts.zone_policy_public_evidence import public_reid_evidence_checks

RESULT_SOURCE = "experiments/results/zone_policy_risk_replay_large_20260801.json"
JsonValue: TypeAlias = bool | int | float | str | None | list["JsonValue"] | dict[str, "JsonValue"]


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
    artifact = cast(dict[str, JsonValue], json.loads(output_path.read_text(encoding="utf-8")))
    return completed, artifact


@pytest.mark.parametrize(
    ("field", "value", "expected_check"),
    [
        ("seed", True, "seed_is_strict_integer"),
        ("maxScans", "8", "replay_contract_valid"),
        ("sensitivity", 0.01, "operating_point_schema_valid"),
        ("kind", "project CCTV causal proof", "replay_contract_valid"),
        (
            "reason",
            "Project CCTV causal improvement confirmed.",
            "promotion_claim_contract_is_exact",
        ),
    ],
)
def test_validator_rejects_exact_contract_tampering(
    tmp_path: Path,
    field: str,
    value: JsonValue,
    expected_check: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    replay = cast(dict[str, JsonValue], payload["topologyReplayEvidence"])
    promotion = cast(dict[str, JsonValue], payload["promotionDecision"])
    if field == "seed":
        payload[field] = value
    elif field == "sensitivity":
        points = cast(list[JsonValue], replay["operatingPoints"])
        point = cast(dict[str, JsonValue], points[0])
        point[field] = value
    elif field == "reason":
        promotion[field] = value
    else:
        replay[field] = value

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks[expected_check] is False
    assert artifact["passed"] is False


def test_validator_recomputes_aggregate_from_raw_paired_outcomes(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    selected = cast(str, payload["selectedPolicy"])
    replay = cast(dict[str, JsonValue], payload["topologyReplayEvidence"])
    cohort = cast(dict[str, JsonValue], replay["selectionCohort"])
    aggregate = cast(dict[str, JsonValue], cohort["aggregateByPolicy"])
    selected_metrics = cast(dict[str, JsonValue], aggregate[selected])
    selected_metrics["resolvedWithinBudgetRate"] = 0.0

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["summaries_recomputed_from_paired_evidence"] is False
    assert artifact["passed"] is False


def test_validator_rejects_overflowed_json_exponent(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = (repository / RESULT_SOURCE).read_text(encoding="utf-8")
    tampered = source.replace('"seed": 20260806', '"seed": 1e309', 1)
    assert tampered != source
    result_path = tmp_path / "replay.json"
    output_path = tmp_path / "mission.json"
    result_path.write_text(tampered, encoding="utf-8")

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


def test_validator_reports_missing_result_without_traceback(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "mission.json"

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(tmp_path / "missing.json"),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "cannot load result" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not output_path.exists()


def test_validator_rejects_tampered_paired_evidence_digest(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    paired = cast(dict[str, JsonValue], payload["pairedOutcomeEvidence"])
    paired["sha256"] = "0" * 64

    completed, artifact = _run_validator(repository, payload, tmp_path)
    checks = cast(dict[str, JsonValue], artifact["checks"])

    assert completed.returncode == 1
    assert checks["paired_evidence_hash_matches_trusted_digest"] is False
    assert artifact["passed"] is False


def test_public_source_metrics_and_embedded_hash_cannot_be_resealed_together(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    payload = _source_payload(repository)
    evidence = cast(dict[str, JsonValue], payload["publicReidEvidence"])
    source_path = repository / cast(str, evidence["artifact"])
    source = cast(dict[str, JsonValue], json.loads(source_path.read_text(encoding="utf-8")))
    metrics = cast(dict[str, JsonValue], source["testMetrics"])
    metrics["known_rank1"] = 0.91
    copied_source = tmp_path / "resealed-public-evidence.json"
    copied_source.write_text(json.dumps(source), encoding="utf-8")
    copied_hash = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    evidence["artifact"] = copied_source.as_posix()
    evidence["sha256"] = copied_hash
    evidence["knownRank1"] = 0.91
    monkeypatch.setattr(public_evidence_module, "PUBLIC_EVIDENCE_ROOT", tmp_path.resolve())

    path_allowed, source_valid, hash_matches, metrics_match = public_reid_evidence_checks(evidence)

    assert path_allowed is True
    assert source_valid is True
    assert hash_matches is False
    assert metrics_match is True
