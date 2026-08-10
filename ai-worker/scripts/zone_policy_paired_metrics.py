from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

if __package__:
    from scripts.zone_policy_result_schema import (
        POLICIES,
        JsonValue,
        MissionValidationInputError,
        PolicyName,
    )
else:
    from zone_policy_result_schema import (
        POLICIES,
        JsonValue,
        MissionValidationInputError,
        PolicyName,
    )

RawRecord = dict[str, JsonValue]
MetricRecord = dict[str, int | float]
IntervalRecord = dict[str, bool | float]
ComparisonRecord = dict[str, IntervalRecord]


@dataclass(frozen=True, slots=True)
class RecomputedReplay:
    selection_aggregate: dict[str, MetricRecord]
    sealed_aggregate: dict[str, MetricRecord]
    selection_comparisons: dict[str, ComparisonRecord]
    sealed_comparisons: dict[str, ComparisonRecord]
    sealed_by_cell: dict[str, MetricRecord]
    selected_policy: PolicyName


def _required_int(record: RawRecord, key: str) -> int:
    value = record[key]
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    raise MissionValidationInputError(f"paired record {key} is not an integer")


def _numeric_metric(record: RawRecord, key: str) -> float:
    value = record[key]
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    if isinstance(value, int):
        return float(value)
    raise MissionValidationInputError(f"paired record {key} is not numeric")


def _aggregate(records: list[RawRecord]) -> MetricRecord:
    count = len(records)
    if count == 0:
        raise MissionValidationInputError("paired aggregate cannot be empty")
    scans = sorted(_required_int(record, "scansToResolution") for record in records)
    p95_index = min(count - 1, math.ceil(0.95 * count) - 1)

    def rate(key: str) -> float:
        return sum(_numeric_metric(record, key) for record in records) / count

    return {
        "episodes": count,
        "resolvedWithinBudgetRate": round(rate("resolvedWithinBudget"), 6),
        "finalTop1Accuracy": round(rate("finalTop1Correct"), 6),
        "falseZoneActivationRate": round(rate("falseZoneActivation"), 6),
        "meanScansToResolution": round(statistics.fmean(scans), 6),
        "p95ScansToResolution": round(float(scans[p95_index]), 6),
    }


def _difference_interval(values: list[float]) -> IntervalRecord:
    mean = statistics.fmean(values)
    standard_error = statistics.stdev(values) / math.sqrt(len(values))
    radius = 1.96 * standard_error
    lower = mean - radius
    upper = mean + radius
    return {
        "delta": mean,
        "delta95Lower": lower,
        "delta95Upper": upper,
        "includesZero": lower <= 0 <= upper,
    }


def _paired(candidate: list[RawRecord], baseline: list[RawRecord]) -> ComparisonRecord:
    candidate_by_id = {str(record["episodeId"]): record for record in candidate}
    baseline_by_id = {str(record["episodeId"]): record for record in baseline}
    if candidate_by_id.keys() != baseline_by_id.keys():
        raise MissionValidationInputError("paired policy episode IDs do not align")

    def differences(key: str) -> list[float]:
        return [
            _numeric_metric(candidate_by_id[episode_id], key)
            - _numeric_metric(baseline_by_id[episode_id], key)
            for episode_id in sorted(candidate_by_id)
        ]

    return {
        "resolvedWithinBudgetRate": _difference_interval(differences("resolvedWithinBudget")),
        "finalTop1Accuracy": _difference_interval(differences("finalTop1Correct")),
        "falseZoneActivationRate": _difference_interval(differences("falseZoneActivation")),
        "meanScansToResolution": _difference_interval(differences("scansToResolution")),
    }


def recompute(records: list[RawRecord]) -> RecomputedReplay:
    grouped: dict[tuple[str, str], list[RawRecord]] = {}
    sealed_cells: dict[tuple[str, str, str], list[RawRecord]] = {}
    for record in records:
        cohort = str(record["cohort"])
        policy = str(record["policy"])
        grouped.setdefault((cohort, policy), []).append(record)
        if cohort == "sealed_test":
            cell = (str(record["scenario"]), str(record["operatingPoint"]), policy)
            sealed_cells.setdefault(cell, []).append(record)

    selection = {policy: _aggregate(grouped[("selection", policy)]) for policy in POLICIES}
    sealed = {policy: _aggregate(grouped[("sealed_test", policy)]) for policy in POLICIES}

    def comparisons(cohort: str) -> dict[str, ComparisonRecord]:
        baseline = grouped[(cohort, "deployed_runtime")]
        return {
            policy: _paired(grouped[(cohort, policy)], baseline)
            for policy in POLICIES
            if policy != "deployed_runtime"
        }

    sealed_by_cell = {
        f"{scenario}/{point}/{policy}": _aggregate(cell_records)
        for (scenario, point, policy), cell_records in sealed_cells.items()
    }
    selected = min(
        POLICIES,
        key=lambda policy: (
            -float(selection[policy]["resolvedWithinBudgetRate"]),
            float(selection[policy]["falseZoneActivationRate"]),
            float(selection[policy]["meanScansToResolution"]),
        ),
    )
    return RecomputedReplay(
        selection_aggregate=selection,
        sealed_aggregate=sealed,
        selection_comparisons=comparisons("selection"),
        sealed_comparisons=comparisons("sealed_test"),
        sealed_by_cell=sealed_by_cell,
        selected_policy=selected,
    )

