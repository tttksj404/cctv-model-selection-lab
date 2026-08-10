import json
from pathlib import Path

from scripts.audit_chirla_protocol import audit_protocol


def _row(
    *,
    role: str,
    identity: str,
    camera: str,
    sequence: str,
) -> dict[str, str]:
    return {
        "benchmarkRole": role,
        "identityGroupId": identity,
        "cameraId": camera,
        "sequenceId": sequence,
    }


def test_audit_reports_overlap_and_strictly_eligible_queries(
    tmp_path: Path,
) -> None:
    rows = [
        _row(role="gallery", identity="person-1", camera="cam-a", sequence="seq-a"),
        _row(role="gallery", identity="person-1", camera="cam-b", sequence="seq-b"),
        _row(role="query", identity="person-1", camera="cam-a", sequence="seq-a"),
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = audit_protocol(manifest)

    assert result["eligibleQueryCount"] == 1
    assert result["queriesWithSameCameraPositive"] == 1
    assert result["queriesWithSameSequencePositive"] == 1
    assert result["strictCrossCameraSequenceEligibleQueries"] == 1
    assert result["strictCrossCameraSequenceEvaluationAvailable"] is True


def test_audit_blocks_strict_protocol_without_cross_domain_positive(
    tmp_path: Path,
) -> None:
    rows = [
        _row(role="gallery", identity="person-1", camera="cam-a", sequence="seq-a"),
        _row(role="query", identity="person-1", camera="cam-a", sequence="seq-a"),
    ]
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    result = audit_protocol(manifest)

    assert result["strictCrossCameraSequenceEligibleQueries"] == 0
    assert result["strictCrossCameraSequenceEvaluationAvailable"] is False

