from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

if __package__:
    from scripts.zone_policy_result_schema import (
        EXPECTED_PUBLIC_REID_CANONICAL_SHA256,
        JsonScalar,
        JsonValue,
        MissionValidationInputError,
        canonical_json_sha256_value,
        finite_float,
        parse_json_bytes,
        same_scalar,
        strict_int,
    )
else:
    from zone_policy_result_schema import (
        EXPECTED_PUBLIC_REID_CANONICAL_SHA256,
        JsonScalar,
        JsonValue,
        MissionValidationInputError,
        canonical_json_sha256_value,
        finite_float,
        parse_json_bytes,
        same_scalar,
        strict_int,
    )

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
PUBLIC_EVIDENCE_ROOT = (REPOSITORY_ROOT / "experiments" / "results" / "evidence").resolve()
PUBLIC_EVIDENCE_FIELDS = frozenset(
    {
        "artifact",
        "sha256",
        "dataset",
        "sealedTestEvaluationCount",
        "knownQueries",
        "distractorQueries",
        "knownRank1",
        "knownRecallAt5",
        "distractorFalseMatchRate",
        "automaticDecisionAccuracy",
        "projectCctvEvidence",
    }
)


def _source_scalar(
    source: Mapping[str, JsonValue],
    key: str,
) -> JsonScalar:
    value = source.get(key)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    return None


def public_reid_evidence_checks(
    evidence: Mapping[str, JsonValue],
) -> tuple[bool, bool, bool, bool]:
    artifact = evidence.get("artifact")
    if not isinstance(artifact, str):
        return False, False, False, False
    supplied_path = Path(artifact)
    resolved_path = (
        supplied_path.resolve()
        if supplied_path.is_absolute()
        else (REPOSITORY_ROOT / supplied_path).resolve()
    )
    try:
        resolved_path.relative_to(PUBLIC_EVIDENCE_ROOT)
    except ValueError:
        return False, False, False, False
    if not resolved_path.is_file():
        return True, False, False, False

    try:
        source_value = parse_json_bytes(
            resolved_path.read_bytes(), label=f"public ReID evidence {resolved_path}"
        )
    except (OSError, MissionValidationInputError):
        return True, False, False, False
    if not isinstance(source_value, dict):
        return True, False, False, False
    source = source_value
    test_metrics_value = source.get("testMetrics")
    if not isinstance(test_metrics_value, dict):
        return True, False, False, False
    test_metrics = test_metrics_value

    sealed_count = strict_int(_source_scalar(source, "sealedTestEvaluationCount"))
    source_numeric_schema_valid = bool(
        sealed_count is not None
        and all(
            strict_int(test_metrics.get(key)) is not None
            for key in ("known_queries", "distractor_queries")
        )
        and all(
            (number := finite_float(test_metrics.get(key))) is not None and 0 <= number <= 1
            for key in (
                "known_rank1",
                "known_recall_at5",
                "distractor_false_match_rate",
                "automatic_decision_accuracy",
            )
        )
    )
    source_valid = bool(
        _source_scalar(source, "schemaVersion") == "prid2011-solider-open-set-v3-summary"
        and _source_scalar(source, "status") == "valid"
        and _source_scalar(source, "cacheMetadataValidated") is True
        and source_numeric_schema_valid
    )
    expected_metrics: dict[str, JsonScalar] = {
        "dataset": "PRID2011 public cross-camera proxy",
        "sealedTestEvaluationCount": sealed_count,
        "knownQueries": _source_scalar(test_metrics, "known_queries"),
        "distractorQueries": _source_scalar(test_metrics, "distractor_queries"),
        "knownRank1": _source_scalar(test_metrics, "known_rank1"),
        "knownRecallAt5": _source_scalar(test_metrics, "known_recall_at5"),
        "distractorFalseMatchRate": _source_scalar(test_metrics, "distractor_false_match_rate"),
        "automaticDecisionAccuracy": _source_scalar(test_metrics, "automatic_decision_accuracy"),
        "projectCctvEvidence": False,
    }
    metrics_match = bool(
        set(evidence) == set(PUBLIC_EVIDENCE_FIELDS)
        and all(same_scalar(evidence.get(key), value) for key, value in expected_metrics.items())
    )
    canonical_hash = canonical_json_sha256_value(source_value)
    hash_matches = bool(
        canonical_hash == EXPECTED_PUBLIC_REID_CANONICAL_SHA256
        and evidence.get("sha256") == EXPECTED_PUBLIC_REID_CANONICAL_SHA256
    )
    return True, source_valid, hash_matches, metrics_match

