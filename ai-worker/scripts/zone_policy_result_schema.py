from __future__ import annotations

import importlib
from collections.abc import Mapping
from typing import TypeAlias

if __package__:
    from scripts import zone_policy_registry as _registry
    from scripts.zone_policy_json import (
        JsonScalar,
        JsonValue,
        MissionValidationInputError,
        canonical_json_sha256,
        canonical_json_sha256_value,
        finite_float,
        json_exact_equal,
        load_json,
        parse_json_bytes,
        parse_json_text,
        same_scalar,
        strict_int,
    )
    from scripts.zone_policy_registry import PolicyName
else:
    import zone_policy_registry as _registry
    from zone_policy_json import (
        JsonScalar,
        JsonValue,
        MissionValidationInputError,
        canonical_json_sha256,
        canonical_json_sha256_value,
        finite_float,
        json_exact_equal,
        load_json,
        parse_json_bytes,
        parse_json_text,
        same_scalar,
        strict_int,
    )
    from zone_policy_registry import PolicyName

EXPECTED_MAX_SCANS = _registry.EXPECTED_MAX_SCANS
EXPECTED_PAIRED_EVIDENCE_SHA256 = _registry.EXPECTED_PAIRED_EVIDENCE_SHA256
EXPECTED_PUBLIC_REID_CANONICAL_SHA256 = _registry.EXPECTED_PUBLIC_REID_CANONICAL_SHA256
IMPLEMENTED_RUNTIME_POLICIES = _registry.IMPLEMENTED_RUNTIME_POLICIES
OPERATING_POINT_VALUES = _registry.OPERATING_POINT_VALUES
POLICIES = _registry.POLICIES
PROMOTION_REASON = _registry.PROMOTION_REASON
REPLAY_KIND = _registry.REPLAY_KIND
RUNTIME_POLICY_IDS = _registry.RUNTIME_POLICY_IDS
RUNTIME_POLICY_IMPLEMENTATIONS = _registry.RUNTIME_POLICY_IMPLEMENTATIONS
SCENARIOS = _registry.SCENARIOS

METRIC_FIELDS = frozenset(
    {
        "episodes",
        "resolvedWithinBudgetRate",
        "finalTop1Accuracy",
        "falseZoneActivationRate",
        "meanScansToResolution",
        "p95ScansToResolution",
    }
)
PAIRED_METRICS = frozenset(
    {
        "resolvedWithinBudgetRate",
        "finalTop1Accuracy",
        "falseZoneActivationRate",
        "meanScansToResolution",
    }
)
INTERVAL_FIELDS = frozenset({"delta", "delta95Lower", "delta95Upper", "includesZero"})
EXPECTED_SCENARIOS = frozenset(SCENARIOS)
IntervalLike: TypeAlias = Mapping[str, bool | float]
ComparisonLike: TypeAlias = Mapping[str, IntervalLike]
_TRUSTED_RUNTIME_TARGETS = frozenset(
    {
        (
            "deployed_runtime",
            "qwen_backend.zone_probability",
            "assess_zone_probability",
        )
    }
)


def runtime_policy_implemented(policy: str) -> bool:
    implementation = next(
        (
            target
            for registered_policy, target in RUNTIME_POLICY_IMPLEMENTATIONS.items()
            if registered_policy == policy
        ),
        None,
    )
    if implementation is None:
        return False
    module_name, attribute_name = implementation
    if (policy, module_name, attribute_name) not in _TRUSTED_RUNTIME_TARGETS:
        return False
    module = importlib.import_module(module_name)
    return callable(getattr(module, attribute_name, None))


def metric_record_valid(value: JsonValue, *, expected_episodes: int) -> bool:
    if not isinstance(value, dict) or set(value) != set(METRIC_FIELDS):
        return False
    episodes = strict_int(value.get("episodes"))
    rates = (
        finite_float(value.get("resolvedWithinBudgetRate")),
        finite_float(value.get("finalTop1Accuracy")),
        finite_float(value.get("falseZoneActivationRate")),
    )
    scans = (
        finite_float(value.get("meanScansToResolution")),
        finite_float(value.get("p95ScansToResolution")),
    )
    return bool(
        episodes == expected_episodes
        and all(number is not None and 0 <= number <= 1 for number in rates)
        and all(number is not None and 0 <= number <= 9 for number in scans)
    )


def aggregate_map_valid(value: JsonValue, *, expected_episodes: int) -> bool:
    return bool(
        isinstance(value, dict)
        and set(value) == set(RUNTIME_POLICY_IDS)
        and all(
            metric_record_valid(metrics, expected_episodes=expected_episodes)
            for metrics in value.values()
        )
    )


def _interval_valid(value: JsonValue) -> bool:
    if not isinstance(value, dict) or set(value) != set(INTERVAL_FIELDS):
        return False
    delta = finite_float(value.get("delta"))
    lower = finite_float(value.get("delta95Lower"))
    upper = finite_float(value.get("delta95Upper"))
    includes_zero = value.get("includesZero")
    return bool(
        delta is not None
        and lower is not None
        and upper is not None
        and isinstance(includes_zero, bool)
        and lower <= delta <= upper
        and includes_zero is (lower <= 0 <= upper)
    )


def paired_comparisons_valid(value: JsonValue) -> bool:
    candidate_policies = set(RUNTIME_POLICY_IDS) - {"deployed_runtime"}
    return bool(
        isinstance(value, dict)
        and set(value) == candidate_policies
        and all(
            isinstance(comparison, dict)
            and set(comparison) == set(PAIRED_METRICS)
            and all(_interval_valid(interval) for interval in comparison.values())
            for comparison in value.values()
        )
    )


def operating_points_valid(value: JsonValue) -> bool:
    if not isinstance(value, list) or len(value) != len(OPERATING_POINT_VALUES):
        return False
    for point, expected in zip(value, OPERATING_POINT_VALUES, strict=True):
        if not isinstance(point, dict) or set(point) != {
            "name",
            "sensitivity",
            "false_positive_rate",
            "unavailable_rate",
        }:
            return False
        name, sensitivity, false_positive_rate, unavailable_rate = expected
        expected_point: dict[str, JsonValue] = {
            "name": name,
            "sensitivity": sensitivity,
            "false_positive_rate": false_positive_rate,
            "unavailable_rate": unavailable_rate,
        }
        if not json_exact_equal(point, expected_point):
            return False
    return True


def _interval_bound(
    comparison: Mapping[str, JsonValue] | ComparisonLike,
    metric: str,
    bound: str,
) -> float | None:
    interval = comparison.get(metric)
    if not isinstance(interval, dict):
        return None
    return finite_float(interval.get(bound))


def passes_paired_promotion_gate(
    comparison: Mapping[str, JsonValue] | ComparisonLike,
) -> bool:
    resolved_lower = _interval_bound(comparison, "resolvedWithinBudgetRate", "delta95Lower")
    false_activation_upper = _interval_bound(comparison, "falseZoneActivationRate", "delta95Upper")
    top1_lower = _interval_bound(comparison, "finalTop1Accuracy", "delta95Lower")
    return bool(
        resolved_lower is not None
        and false_activation_upper is not None
        and top1_lower is not None
        and resolved_lower > 0
        and false_activation_upper <= 0
        and top1_lower >= 0
    )


__all__ = [
    "EXPECTED_MAX_SCANS",
    "EXPECTED_PAIRED_EVIDENCE_SHA256",
    "EXPECTED_PUBLIC_REID_CANONICAL_SHA256",
    "EXPECTED_SCENARIOS",
    "IMPLEMENTED_RUNTIME_POLICIES",
    "OPERATING_POINT_VALUES",
    "POLICIES",
    "PROMOTION_REASON",
    "REPLAY_KIND",
    "RUNTIME_POLICY_IDS",
    "SCENARIOS",
    "JsonScalar",
    "JsonValue",
    "MissionValidationInputError",
    "PolicyName",
    "aggregate_map_valid",
    "canonical_json_sha256",
    "canonical_json_sha256_value",
    "finite_float",
    "json_exact_equal",
    "load_json",
    "metric_record_valid",
    "operating_points_valid",
    "paired_comparisons_valid",
    "parse_json_bytes",
    "parse_json_text",
    "passes_paired_promotion_gate",
    "runtime_policy_implemented",
    "same_scalar",
    "strict_int",
]
