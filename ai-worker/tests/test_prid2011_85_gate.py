from __future__ import annotations

import json
from pathlib import Path
from typing import TypedDict

from scripts.evaluate_solider_90_gate import evaluate_prid2011_85


class PromotionContract(TypedDict):
    crossCamera: bool
    identityDisjoint: bool
    sealedTest: bool
    thresholdSelectedOnValidationOnly: bool


class TrackCounts(TypedDict):
    test: int
    validation: int


class SealedTestMetrics(TypedDict):
    automatic_decision_accuracy: float
    distractor_false_match_rate: float
    distractor_queries: int
    false_reject_rate: float
    known_queries: int
    known_rank1: float
    known_recall_at5: float
    query_tracks: int


class PridPayload(TypedDict):
    schemaVersion: str
    status: str
    promotionContract: PromotionContract
    trackCounts: TrackCounts
    testMetrics: SealedTestMetrics


def valid_prid_payload() -> PridPayload:
    return {
        "schemaVersion": "prid2011-track-evaluation-v1",
        "status": "valid",
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": True,
        },
        "trackCounts": {"test": 787, "validation": 187},
        "testMetrics": {
            "automatic_decision_accuracy": 0.86,
            "distractor_false_match_rate": 0.04,
            "distractor_queries": 148,
            "false_reject_rate": 0.14,
            "known_queries": 100,
            "known_rank1": 0.86,
            "known_recall_at5": 0.96,
            "query_tracks": 248,
        },
    }


def write_payload(tmp_path: Path, payload: PridPayload) -> Path:
    path = tmp_path / "prid-result.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_prid_gate_passes_complete_sealed_identity_result(tmp_path: Path) -> None:
    status, reasons = evaluate_prid2011_85(
        write_payload(tmp_path, valid_prid_payload())
    )

    assert status == "PASS"
    assert reasons == ["PRID2011 generalized 85% contract satisfied"]


def test_prid_gate_fails_current_open_set_error_rates(tmp_path: Path) -> None:
    payload = valid_prid_payload()
    payload["testMetrics"]["automatic_decision_accuracy"] = 0.7177
    payload["testMetrics"]["distractor_false_match_rate"] = 0.3041
    payload["testMetrics"]["false_reject_rate"] = 0.21

    status, reasons = evaluate_prid2011_85(write_payload(tmp_path, payload))

    assert status == "FAIL"
    assert reasons == [
        "automatic_decision_accuracy=0.717700 is below 0.850000",
        "distractor_false_match_rate=0.304100 exceeds 0.050000",
        "false_reject_rate=0.210000 exceeds 0.150000",
    ]


def test_prid_gate_blocks_nonsealed_or_leaky_protocol(tmp_path: Path) -> None:
    payload = valid_prid_payload()
    payload["promotionContract"]["sealedTest"] = False
    payload["promotionContract"]["thresholdSelectedOnValidationOnly"] = False

    status, reasons = evaluate_prid2011_85(write_payload(tmp_path, payload))

    assert status == "BLOCKED"
    assert reasons == [
        "sealed independent test contract is not satisfied: "
        "sealedTest, thresholdSelectedOnValidationOnly"
    ]


def test_prid_gate_blocks_small_query_set(tmp_path: Path) -> None:
    payload = valid_prid_payload()
    payload["testMetrics"]["known_queries"] = 20
    payload["testMetrics"]["distractor_queries"] = 37

    status, reasons = evaluate_prid2011_85(write_payload(tmp_path, payload))

    assert status == "BLOCKED"
    assert reasons == [
        "test set requires at least 100 known and 100 distractor queries"
    ]

