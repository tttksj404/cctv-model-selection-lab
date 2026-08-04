from __future__ import annotations

import argparse
import math
import re
import sys
from pathlib import Path
from typing import Final, TypeAlias

from pydantic import JsonValue, TypeAdapter, ValidationError

JsonObject: TypeAlias = dict[str, JsonValue]
JSON_OBJECT_ADAPTER: Final = TypeAdapter(JsonObject)

THRESHOLD = 0.90
REQUIRED_METRICS = ("top1_accuracy", "track_exact_match", "mA", "InsF1")
REQUIRED_PROVENANCE = (
    "sealedTestManifestSha256",
    "identityLabelSha256",
    "splitMethod",
    "metricImplementation",
)
HASH_PROVENANCE = ("sealedTestManifestSha256", "identityLabelSha256")
PRID_REQUIRED_PROTOCOL = (
    "crossCamera",
    "identityDisjoint",
    "sealedTest",
    "thresholdSelectedOnValidationOnly",
)
PRID_MINIMUM_METRICS = (
    ("automatic_decision_accuracy", 0.85),
    ("known_rank1", 0.85),
    ("known_recall_at5", 0.95),
)
PRID_MAXIMUM_METRICS = (
    ("distractor_false_match_rate", 0.05),
    ("false_reject_rate", 0.15),
)


def _read_bool(
    mapping: JsonObject, key: str, default: JsonValue = None
) -> JsonValue:
    return mapping.get(key, default)


def _finite_metric(value: JsonValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float | str):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(parsed) or not 0.0 <= parsed <= 1.0:
        return None
    return parsed


def _nonnegative_integer(value: JsonValue) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def evaluate(result_path: Path) -> tuple[str, list[str]]:
    payload = JSON_OBJECT_ADAPTER.validate_json(
        result_path.read_text(encoding="utf-8")
    )
    eligibility = payload.get("evaluationEligibility")
    if not isinstance(eligibility, dict):
        return "BLOCKED", ["evaluation eligibility contract is missing"]

    if (
        _read_bool(eligibility, "identityLabelsAvailable") is not True
    ):
        return "BLOCKED", ["reviewed CCTV identity/track labels are unavailable"]
    if _read_bool(eligibility, "trackHeldoutMetricsEligible") is not True:
        return "BLOCKED", ["track-heldout attribute metrics are unavailable"]
    if _read_bool(eligibility, "proxyMetricsReusedAsIdentity") is not False:
        return "BLOCKED", ["proxy metrics are not explicitly excluded from the identity gate"]

    if payload.get("measurementStatus") != "identity_measured_sealed_test":
        return "BLOCKED", ["result is not marked as an identity-measured sealed test"]

    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return "BLOCKED", ["sealed-test provenance is missing"]
    missing_provenance: list[str] = []
    for name in REQUIRED_PROVENANCE:
        value = provenance.get(name)
        if not isinstance(value, str) or not value.strip():
            missing_provenance.append(name)
    if missing_provenance:
        return "BLOCKED", [
            "sealed-test provenance fields are missing: "
            + ", ".join(missing_provenance)
        ]
    invalid_hashes: list[str] = []
    for name in HASH_PROVENANCE:
        value = provenance[name]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", value):
            invalid_hashes.append(name)
    if invalid_hashes:
        return "BLOCKED", ["provenance hashes are not SHA-256: " + ", ".join(invalid_hashes)]

    metrics_container = payload.get("metrics", {})
    test_metrics: JsonObject = {}
    if isinstance(metrics_container, dict):
        test_candidate = metrics_container.get("test")
        if isinstance(test_candidate, dict):
            test_metrics = test_candidate

    missing = [name for name in REQUIRED_METRICS if name not in test_metrics]
    if missing:
        return "FAIL", [f"missing test metrics: {', '.join(missing)}"]

    invalid = [
        f"{name}={test_metrics[name]!r}"
        for name in REQUIRED_METRICS
        if _finite_metric(test_metrics[name]) is None
    ]
    if invalid:
        return "FAIL", ["invalid finite test metrics: " + ", ".join(invalid)]

    below: list[str] = []
    for name in REQUIRED_METRICS:
        value = _finite_metric(test_metrics[name])
        if value is not None and value < THRESHOLD:
            below.append(f"{name}={value:.6f}")
    if below:
        return "FAIL", ["90% threshold not met: " + ", ".join(below)]
    return "PASS", ["SOLIDER 90% contract satisfied on the sealed test split"]


def evaluate_prid2011_85(result_path: Path) -> tuple[str, list[str]]:
    payload = JSON_OBJECT_ADAPTER.validate_json(
        result_path.read_text(encoding="utf-8")
    )
    if payload.get("schemaVersion") != "prid2011-track-evaluation-v1":
        return "BLOCKED", ["PRID2011 track evaluation schema is missing"]
    if payload.get("status") != "valid":
        return "BLOCKED", ["PRID2011 track evaluation status is not valid"]

    protocol = payload.get("promotionContract")
    if not isinstance(protocol, dict):
        return "BLOCKED", ["promotion contract is missing"]
    missing_protocol = [
        field for field in PRID_REQUIRED_PROTOCOL if _read_bool(protocol, field) is not True
    ]
    if missing_protocol:
        return "BLOCKED", [
            "sealed independent test contract is not satisfied: "
            + ", ".join(missing_protocol)
        ]

    test_metrics = payload.get("testMetrics")
    if not isinstance(test_metrics, dict):
        return "FAIL", ["test metrics are missing"]
    known_queries = _nonnegative_integer(test_metrics.get("known_queries"))
    distractor_queries = _nonnegative_integer(test_metrics.get("distractor_queries"))
    if (
        known_queries is None
        or distractor_queries is None
        or known_queries < 100
        or distractor_queries < 100
    ):
        return "BLOCKED", [
            "test set requires at least 100 known and 100 distractor queries"
        ]

    failures: list[str] = []
    for name, minimum in PRID_MINIMUM_METRICS:
        value = _finite_metric(test_metrics.get(name))
        if value is None:
            failures.append(f"{name} is missing or invalid")
        elif value < minimum:
            failures.append(f"{name}={value:.6f} is below {minimum:.6f}")
    for name, maximum in PRID_MAXIMUM_METRICS:
        value = _finite_metric(test_metrics.get(name))
        if value is None:
            failures.append(f"{name} is missing or invalid")
        elif value > maximum:
            failures.append(f"{name}={value:.6f} exceeds {maximum:.6f}")
    if failures:
        return "FAIL", failures
    return "PASS", ["PRID2011 generalized 85% contract satisfied"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--prid2011-85", action="store_true")
    args = parser.parse_args()
    try:
        evaluator = evaluate_prid2011_85 if args.prid2011_85 else evaluate
        status, reasons = evaluator(args.result)
    except (OSError, TypeError, ValidationError, ValueError) as exc:
        print(f"FAIL: cannot evaluate result JSON: {exc}")
        return 2

    for reason in reasons:
        print(f"{status}: {reason}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
