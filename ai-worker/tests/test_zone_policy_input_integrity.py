from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import zlib
from pathlib import Path
from typing import TypeAlias, cast

import pytest

import scripts.zone_policy_paired_evidence as paired_evidence_module
import scripts.zone_policy_result_schema as result_schema
from scripts.zone_policy_json import MissionValidationInputError, parse_json_text
from scripts.zone_policy_paired_evidence import EvidenceSpec, validate_and_recompute
from scripts.zone_policy_public_evidence import public_reid_evidence_checks
from scripts.zone_policy_replay_seed import expected_target_state
from scripts.zone_policy_result_schema import JsonValue

RESULT_SOURCE = "experiments/results/zone_policy_risk_replay_large_20260801.json"
PAIRED_SOURCE = "experiments/results/evidence/zone_policy_paired_outcomes_20260801.jsonl.zlib"
RECEIPT_SOURCE = "experiments/results/evidence/zone_policy_replay_run_receipts_20260801.json"
TestJsonValue: TypeAlias = (
    bool | int | float | str | None | list["TestJsonValue"] | dict[str, "TestJsonValue"]
)
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def _run_validator(
    repository: Path, source: str, tmp_path: Path
) -> subprocess.CompletedProcess[str]:
    result_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    result_path.write_text(source, encoding="utf-8")
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
    assert not output_path.exists()
    return completed


@pytest.mark.parametrize("source", ["{", "[]", "{}"])
def test_validator_rejects_malformed_or_incomplete_json_without_traceback(
    tmp_path: Path, source: str
) -> None:
    repository = Path(__file__).resolve().parents[1]
    completed = _run_validator(repository, source, tmp_path)

    assert completed.returncode == 2
    assert "cannot load result" in completed.stderr
    assert "Traceback" not in completed.stderr


def test_duplicate_json_object_key_is_rejected_before_validation(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    source = (repository / RESULT_SOURCE).read_text(encoding="utf-8")
    tampered = source.replace('"status": "valid"', '"status": "valid", "status": "failed"', 1)
    assert tampered != source

    completed = _run_validator(repository, tampered, tmp_path)

    assert completed.returncode == 2
    assert "duplicate JSON object key" in completed.stderr
    assert "Traceback" not in completed.stderr
    with pytest.raises(MissionValidationInputError, match="duplicate JSON object key"):
        parse_json_text('{"outer": {"claim": true, "claim": false}}')


def test_validator_rejects_non_utf8_input_without_traceback(tmp_path: Path) -> None:
    repository = Path(__file__).resolve().parents[1]
    output_path = tmp_path / "output.json"
    completed = subprocess.run(
        [
            sys.executable,
            "scripts/validate_zone_policy_mission.py",
            "--result",
            str(repository / PAIRED_SOURCE),
            "--output",
            str(output_path),
        ],
        cwd=repository,
        check=False,
        capture_output=True,
        text=True,
    )

    assert completed.returncode == 2
    assert "must be valid UTF-8" in completed.stderr
    assert "Traceback" not in completed.stderr
    assert not output_path.exists()


def test_runtime_callable_must_match_the_fixed_trusted_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        result_schema,
        "RUNTIME_POLICY_IMPLEMENTATIONS",
        {"deployed_runtime": ("builtins", "print")},
    )

    assert result_schema.runtime_policy_implemented("deployed_runtime") is False


def test_resealed_target_state_tampering_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repository = Path(__file__).resolve().parents[1]
    result = cast(
        dict[str, TestJsonValue],
        json.loads((repository / RESULT_SOURCE).read_text(encoding="utf-8")),
    )
    source_bytes = (repository / PAIRED_SOURCE).read_bytes()
    records = [
        cast(dict[str, TestJsonValue], json.loads(line))
        for line in zlib.decompress(source_bytes).decode().splitlines()
    ]
    first = records[0]
    episode_key = (first["cohort"], first["episodeId"])
    original_target = first["targetState"]
    replacement_target = 2 if original_target != 2 else 3
    changed = 0
    for record in records:
        if (record["cohort"], record["episodeId"]) == episode_key:
            record["targetState"] = replacement_target
            changed += 1
    assert changed == 12

    tampered_text = (
        "\n".join(
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            for record in records
        )
        + "\n"
    )
    tampered_bytes = zlib.compress(tampered_text.encode(), level=9)
    evidence_root = (tmp_path / "evidence").resolve()
    evidence_root.mkdir()
    tampered_path = evidence_root / "resealed.jsonl.zlib"
    tampered_path.write_bytes(tampered_bytes)
    tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
    monkeypatch.setattr(paired_evidence_module, "REPOSITORY_ROOT", tmp_path.resolve())
    monkeypatch.setattr(paired_evidence_module, "EVIDENCE_ROOT", evidence_root)
    monkeypatch.setattr(paired_evidence_module, "EXPECTED_PAIRED_EVIDENCE_SHA256", tampered_sha)

    replay = cast(dict[str, TestJsonValue], result["topologyReplayEvidence"])
    points = cast(list[TestJsonValue], replay["operatingPoints"])
    evidence: dict[str, JsonValue] = {
        "artifact": "evidence/resealed.jsonl.zlib",
        "format": "jsonl-zlib-v1",
        "recordCount": len(records),
        "sha256": tampered_sha,
    }
    path_allowed, hash_matches, recomputed = validate_and_recompute(
        evidence,
        EvidenceSpec(
            base_seed=cast(int, result["seed"]),
            episodes_per_cell=cast(int, result["episodesPerCellPerCohort"]),
            scenarios=tuple(cast(list[str], replay["scenarios"])),
            operating_points=tuple(
                cast(str, cast(dict[str, TestJsonValue], point)["name"]) for point in points
            ),
        ),
    )

    assert path_allowed is True
    assert hash_matches is True
    assert recomputed is None


def test_every_sealed_target_is_derived_from_its_cell_seed() -> None:
    repository = Path(__file__).resolve().parents[1]
    records = [
        cast(dict[str, TestJsonValue], json.loads(line))
        for line in zlib.decompress((repository / PAIRED_SOURCE).read_bytes()).decode().splitlines()
    ]

    assert all(
        record["targetState"]
        == expected_target_state(cast(int, record["cellSeed"]), cast(str, record["scenario"]))
        for record in records
    )


def test_trusted_evidence_is_hashed_and_parsed_from_one_file_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    result = cast(
        dict[str, JsonValue],
        json.loads((repository / RESULT_SOURCE).read_text(encoding="utf-8")),
    )
    public = cast(dict[str, JsonValue], result["publicReidEvidence"])
    paired = cast(dict[str, JsonValue], result["pairedOutcomeEvidence"])
    replay = cast(dict[str, JsonValue], result["topologyReplayEvidence"])
    points = cast(list[JsonValue], replay["operatingPoints"])
    watched = {
        (repository / cast(str, public["artifact"])).resolve(): 0,
        (repository / cast(str, paired["artifact"])).resolve(): 0,
    }
    original_read_bytes = Path.read_bytes

    def counted_read_bytes(path: Path) -> bytes:
        resolved = path.resolve()
        if resolved in watched:
            watched[resolved] += 1
        return original_read_bytes(path)

    monkeypatch.setattr(Path, "read_bytes", counted_read_bytes)

    assert public_reid_evidence_checks(public) == (True, True, True, True)
    path_allowed, hash_matches, recomputed = validate_and_recompute(
        paired,
        EvidenceSpec(
            base_seed=cast(int, result["seed"]),
            episodes_per_cell=cast(int, result["episodesPerCellPerCohort"]),
            scenarios=tuple(cast(list[str], replay["scenarios"])),
            operating_points=tuple(
                cast(str, cast(dict[str, JsonValue], point)["name"]) for point in points
            ),
        ),
    )

    assert path_allowed is True
    assert hash_matches is True
    assert recomputed is not None
    assert set(watched.values()) == {1}


def _assert_run_receipt_contract(
    receipt_value: JsonValue,
) -> tuple[dict[str, JsonValue], list[dict[str, JsonValue]], dict[str, JsonValue]]:
    assert isinstance(receipt_value, dict)
    receipt = receipt_value
    assert set(receipt) == {"schemaVersion", "environment", "runs", "attestationBoundary"}
    assert receipt["schemaVersion"] == "eyesonu-zone-policy-run-receipts-v2"
    environment = receipt["environment"]
    assert isinstance(environment, dict)
    assert environment == {
        "python": "3.14.6",
        "execution": "cpu-deterministic-policy-replay",
    }
    runs_value = receipt["runs"]
    assert isinstance(runs_value, list)
    assert len(runs_value) == 3
    assert all(isinstance(run, dict) for run in runs_value)
    runs = cast(list[dict[str, JsonValue]], runs_value)
    base_run_fields = {
        "captureId",
        "commandSha256",
        "exactCommandRecorded",
        "durationMilliseconds",
        "stdoutSha256",
    }
    assert all(set(run) == base_run_fields for run in runs[:2])
    assert set(runs[-1]) == base_run_fields | {"command", "artifacts"}

    capture_ids: list[str] = []
    stdout_digests: list[str] = []
    exact_command_flags: list[bool] = []
    for run in runs:
        capture_id = run["captureId"]
        command_digest = run["commandSha256"]
        exact_command_recorded = run["exactCommandRecorded"]
        duration = run["durationMilliseconds"]
        stdout_digest = run["stdoutSha256"]
        assert isinstance(capture_id, str) and capture_id
        assert isinstance(command_digest, str) and SHA256_PATTERN.fullmatch(command_digest)
        assert isinstance(exact_command_recorded, bool)
        assert type(duration) is int and duration > 0
        assert isinstance(stdout_digest, str) and SHA256_PATTERN.fullmatch(stdout_digest)
        capture_ids.append(capture_id)
        stdout_digests.append(stdout_digest)
        exact_command_flags.append(exact_command_recorded)

    assert exact_command_flags == [False, False, True]
    assert len(set(capture_ids)) == len(runs)
    assert len(set(stdout_digests)) == 1

    final_run = runs[-1]
    command = final_run["command"]
    assert isinstance(command, str)
    assert final_run["commandSha256"] == hashlib.sha256(command.encode()).hexdigest()
    artifacts_value = final_run["artifacts"]
    assert isinstance(artifacts_value, dict)
    artifacts = artifacts_value
    assert set(artifacts) == {
        "pairedEvidenceSha256",
        "replayRawSha256",
        "replayCanonicalSha256",
    }
    assert all(
        isinstance(digest, str) and SHA256_PATTERN.fullmatch(digest)
        for digest in artifacts.values()
    )
    attestation_boundary = receipt["attestationBoundary"]
    assert attestation_boundary == (
        "Repository-tracked local run receipt; not an independent protected-CI attestation."
    )
    return receipt, runs, artifacts


def test_run_receipt_matches_the_tracked_replay_artifacts() -> None:
    repository = Path(__file__).resolve().parents[1]
    replay_path = repository / RESULT_SOURCE
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    receipt_value = parse_json_text((repository / RECEIPT_SOURCE).read_text(encoding="utf-8"))
    _, _, artifacts = _assert_run_receipt_contract(receipt_value)
    canonical = json.dumps(replay, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    assert artifacts["pairedEvidenceSha256"] == replay["pairedOutcomeEvidence"]["sha256"]
    assert artifacts["replayRawSha256"] == hashlib.sha256(replay_path.read_bytes()).hexdigest()
    assert artifacts["replayCanonicalSha256"] == hashlib.sha256(canonical.encode()).hexdigest()


@pytest.mark.parametrize(
    ("original", "replacement"),
    [
        ('"python": "3.14.6"', '"python": "3.14.6", "extra": true'),
        ('"captureId": "20260801-172508728-4fcb0941"', '"captureId": 1'),
        ('"durationMilliseconds": 436862', '"durationMilliseconds": 436862.0'),
        ('"durationMilliseconds": 436862', '"durationMilliseconds": true'),
        ('"exactCommandRecorded": false', '"exactCommandRecorded": 0'),
        (
            '"stdoutSha256": "3323a42ea4de3cd936c5d42b1c64fa958f63e3c6570aae6f4da2403ae5524c92"',
            '"stdoutSha256": 1',
        ),
    ],
)
def test_run_receipt_contract_rejects_scalar_type_mutations(
    original: str,
    replacement: str,
) -> None:
    repository = Path(__file__).resolve().parents[1]
    receipt_text = (repository / RECEIPT_SOURCE).read_text(encoding="utf-8")
    mutated = parse_json_text(receipt_text.replace(original, replacement, 1))

    with pytest.raises(AssertionError):
        _assert_run_receipt_contract(mutated)


def test_run_receipt_contract_rejects_duplicate_json_keys() -> None:
    repository = Path(__file__).resolve().parents[1]
    receipt_text = (repository / RECEIPT_SOURCE).read_text(encoding="utf-8")
    duplicated = receipt_text.replace(
        '"schemaVersion": "eyesonu-zone-policy-run-receipts-v2"',
        '"schemaVersion": "invalid", "schemaVersion": "eyesonu-zone-policy-run-receipts-v2"',
        1,
    )

    with pytest.raises(MissionValidationInputError, match="duplicate JSON object key"):
        parse_json_text(duplicated)
