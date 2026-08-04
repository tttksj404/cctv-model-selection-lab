from __future__ import annotations

import json
from pathlib import Path

from scripts.evaluate_solider_90_gate import evaluate


def valid_payload() -> dict[str, object]:
    return {
        "measurementStatus": "identity_measured_sealed_test",
        "evaluationEligibility": {
            "identityLabelsAvailable": True,
            "trackHeldoutMetricsEligible": True,
            "proxyMetricsReusedAsIdentity": False,
        },
        "provenance": {
            "sealedTestManifestSha256": "0" * 64,
            "identityLabelSha256": "1" * 64,
            "splitMethod": "identity_group_and_track_heldout",
            "metricImplementation": "cctv_identity_evaluation_v1",
        },
        "metrics": {
            "test": {
                "top1_accuracy": 0.91,
                "track_exact_match": 0.92,
                "mA": 0.93,
                "InsF1": 0.94,
            }
        },
    }


def write_payload(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_gate_blocks_proxy_like_payload_without_sealed_provenance(tmp_path: Path) -> None:
    payload = valid_payload()
    payload.pop("provenance")
    status, reasons = evaluate(write_payload(tmp_path, payload))
    assert status == "BLOCKED"
    assert reasons == ["sealed-test provenance is missing"]


def test_gate_passes_only_complete_sealed_identity_result(tmp_path: Path) -> None:
    status, reasons = evaluate(write_payload(tmp_path, valid_payload()))
    assert status == "PASS"
    assert reasons == ["SOLIDER 90% contract satisfied on the sealed test split"]


def test_gate_blocks_old_root_level_flags(tmp_path: Path) -> None:
    payload = valid_payload()
    payload.pop("evaluationEligibility")
    payload.update(
        {
            "identityLabelsAvailable": True,
            "trackHeldoutMetricsEligible": True,
            "proxyMetricsReusedAsIdentity": False,
        }
    )
    status, reasons = evaluate(write_payload(tmp_path, payload))
    assert status == "BLOCKED"
    assert reasons == ["evaluation eligibility contract is missing"]


def test_gate_blocks_placeholder_provenance_hash(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["provenance"]["sealedTestManifestSha256"] = "manifest-hash"

    status, reasons = evaluate(write_payload(tmp_path, payload))

    assert status == "BLOCKED"
    assert reasons == ["provenance hashes are not SHA-256: sealedTestManifestSha256"]
