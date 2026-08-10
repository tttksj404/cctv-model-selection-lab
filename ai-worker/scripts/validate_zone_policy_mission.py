"""Validate one sealed mission result through a closed check matrix.

# noqa: SIZE_OK
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import cast

if __package__:
    from scripts.zone_policy_paired_evidence import EvidenceSpec, validate_and_recompute
    from scripts.zone_policy_public_evidence import (
        public_reid_evidence_checks as _public_reid_evidence_checks,
    )
    from scripts.zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        OPERATING_POINT_VALUES,
        PROMOTION_REASON,
        REPLAY_KIND,
        RUNTIME_POLICY_IDS,
        SCENARIOS,
        JsonValue,
        MissionValidationInputError,
        json_exact_equal,
        runtime_policy_implemented,
    )
    from scripts.zone_policy_result_schema import (
        aggregate_map_valid as _aggregate_map_valid,
    )
    from scripts.zone_policy_result_schema import (
        finite_float as _finite_float,
    )
    from scripts.zone_policy_result_schema import (
        load_json as _load_json,
    )
    from scripts.zone_policy_result_schema import (
        operating_points_valid as _operating_points_valid,
    )
    from scripts.zone_policy_result_schema import (
        paired_comparisons_valid as _paired_comparisons_valid,
    )
    from scripts.zone_policy_result_schema import (
        passes_paired_promotion_gate as _passes_paired_promotion_gate,
    )
    from scripts.zone_policy_result_schema import (
        strict_int as _strict_int,
    )
else:
    from zone_policy_paired_evidence import EvidenceSpec, validate_and_recompute
    from zone_policy_public_evidence import (
        public_reid_evidence_checks as _public_reid_evidence_checks,
    )
    from zone_policy_result_schema import (
        EXPECTED_MAX_SCANS,
        OPERATING_POINT_VALUES,
        PROMOTION_REASON,
        REPLAY_KIND,
        RUNTIME_POLICY_IDS,
        SCENARIOS,
        JsonValue,
        MissionValidationInputError,
        json_exact_equal,
        runtime_policy_implemented,
    )
    from zone_policy_result_schema import (
        aggregate_map_valid as _aggregate_map_valid,
    )
    from zone_policy_result_schema import (
        finite_float as _finite_float,
    )
    from zone_policy_result_schema import (
        load_json as _load_json,
    )
    from zone_policy_result_schema import (
        operating_points_valid as _operating_points_valid,
    )
    from zone_policy_result_schema import (
        paired_comparisons_valid as _paired_comparisons_valid,
    )
    from zone_policy_result_schema import (
        passes_paired_promotion_gate as _passes_paired_promotion_gate,
    )
    from zone_policy_result_schema import (
        strict_int as _strict_int,
    )

RESULT_KEYS = <redacted>
    {
        "schemaVersion",
        "status",
        "seed",
        "episodesPerCellPerCohort",
        "pairedEpisodeCount",
        "publicReidEvidence",
        "pairedOutcomeEvidence",
        "topologyReplayEvidence",
        "selectedPolicy",
        "selectedRuntimePolicy",
        "selectionMetricOrder",
        "runtimeSafetyContract",
        "runtimeEvidence",
        "promotionDecision",
    }
)
REPLAY_KEYS = <redacted>
    {
        "kind",
        "projectCctvEvidence",
        "synchronizedMultiCameraObservation",
        "scenarios",
        "operatingPoints",
        "maxScans",
        "selectionCohort",
        "sealedTestCohort",
    }
)


def _require_mapping(value: JsonValue, *, label: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise MissionValidationInputError(f"{label} must be a JSON object")
    return value


def _require_keys(
    value: dict[str, JsonValue],
    required: frozenset[str] | set[str],
    *,
    label: str,
) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise MissionValidationInputError(f"{label} is missing keys: {', '.join(missing)}")


def _preflight_result(value: JsonValue) -> dict[str, JsonValue]:
    result = _require_mapping(value, label="result")
    _require_keys(result, RESULT_KEYS, label="result")
    replay = _require_mapping(result["topologyReplayEvidence"], label="topologyReplayEvidence")
    _require_keys(replay, REPLAY_KEYS, label="topologyReplayEvidence")

    selection = _require_mapping(replay["selectionCohort"], label="selectionCohort")
    sealed = _require_mapping(replay["sealedTestCohort"], label="sealedTestCohort")
    selection_keys = {"seedOffset", "aggregateByPolicy", "pairedComparisonsAgainstDeployed"}
    sealed_keys = selection_keys | {"byScenarioAndOperatingPoint"}
    _require_keys(selection, selection_keys, label="selectionCohort")
    _require_keys(sealed, sealed_keys, label="sealedTestCohort")

    for label, cohort in (("selectionCohort", selection), ("sealedTestCohort", sealed)):
        aggregate = _require_mapping(cohort["aggregateByPolicy"], label=f"{label}.aggregate")
        _require_keys(
            aggregate,
            {"static_representative", "deployed_runtime"},
            label=f"{label}.aggregate",
        )
        _require_mapping(aggregate["static_representative"], label=f"{label}.aggregate.static")
        _require_mapping(aggregate["deployed_runtime"], label=f"{label}.aggregate.deployed")
        _require_mapping(cohort["pairedComparisonsAgainstDeployed"], label=f"{label}.comparisons")

    for key in (
        "publicReidEvidence",
        "pairedOutcomeEvidence",
        "runtimeEvidence",
    ):
        _require_mapping(result[key], label=key)
    promotion = _require_mapping(result["promotionDecision"], label="promotionDecision")
    _require_keys(
        promotion,
        {
            "projectCctvGeneralization85Confirmed",
            "cameraUtilityCausalImprovementConfirmed",
            "selectionPairedIntervalPassed",
            "sealedTestPairedIntervalPassed",
            "proxyMaterialImprovementOverDeployedConfirmed",
            "reason",
        },
        label="promotionDecision",
    )
    safety = _require_mapping(result["runtimeSafetyContract"], label="runtimeSafetyContract")
    _require_keys(
        safety,
        {
            "operatorReviewRequired",
            "autoMatchAllowed",
            "probabilityProvenanceRequired",
            "sameTrackEvidenceDeduplicated",
            "staleProbabilityRevisionRejected",
            "trustedRegistryAllowlistRequired",
            "crossCameraCorrelationGroupRequired",
        },
        label="runtimeSafetyContract",
    )
    if not isinstance(result["selectedPolicy"], str):
        raise MissionValidationInputError("selectedPolicy must be a string")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the zone-policy autoresearch mission")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = _preflight_result(_load_json(args.result))
    except (OSError, MissionValidationInputError) as exc:
        parser.error(f"cannot load result: {exc}")
    result_contract_valid = bool(
        set(result) == set(RESULT_KEYS)
        and result.get("schemaVersion") == "eyesonu-zone-policy-replay-v3"
        and result.get("status") == "valid"
    )
    seed = _strict_int(result.get("seed"))
    public_evidence = cast(dict[str, JsonValue], result["publicReidEvidence"])
    (
        public_evidence_path_allowed,
        public_evidence_source_valid,
        public_evidence_hash_matches,
        public_evidence_metrics_match,
    ) = _public_reid_evidence_checks(public_evidence)
    replay = cast(dict[str, JsonValue], result["topologyReplayEvidence"])
    replay_contract_valid = bool(
        set(replay) == set(REPLAY_KEYS)
        and replay.get("kind") == REPLAY_KIND
        and _strict_int(replay.get("maxScans")) == EXPECTED_MAX_SCANS
    )
    selection_cohort = cast(dict[str, JsonValue], replay["selectionCohort"])
    sealed_cohort = cast(dict[str, JsonValue], replay["sealedTestCohort"])
    selection_aggregate = cast(dict[str, JsonValue], selection_cohort["aggregateByPolicy"])
    sealed_aggregate = cast(dict[str, JsonValue], sealed_cohort["aggregateByPolicy"])
    static_baseline = cast(dict[str, JsonValue], sealed_aggregate["static_representative"])
    deployed = cast(dict[str, JsonValue], sealed_aggregate["deployed_runtime"])
    selected_name = cast(str, result["selectedPolicy"])
    selection_comparisons = cast(
        dict[str, JsonValue], selection_cohort["pairedComparisonsAgainstDeployed"]
    )
    sealed_comparisons = cast(
        dict[str, JsonValue], sealed_cohort["pairedComparisonsAgainstDeployed"]
    )
    promotion = cast(dict[str, JsonValue], result["promotionDecision"])
    scenarios = replay["scenarios"]
    operating_points = replay["operatingPoints"]
    episodes_per_cell = _strict_int(result["episodesPerCellPerCohort"], minimum=50)
    scenarios_valid = bool(
        isinstance(scenarios, list)
        and all(isinstance(value, str) for value in scenarios)
        and cast(list[str], scenarios) == list(SCENARIOS)
    )
    operating_points_are_valid = _operating_points_valid(operating_points)
    expected_paired_count = (
        len(cast(list[JsonValue], scenarios))
        * len(cast(list[JsonValue], operating_points))
        * episodes_per_cell
        if scenarios_valid and operating_points_are_valid and episodes_per_cell is not None
        else -1
    )
    paired_evidence = cast(dict[str, JsonValue], result["pairedOutcomeEvidence"])
    paired_evidence_path_allowed, paired_evidence_hash_matches, recomputed = validate_and_recompute(
        paired_evidence,
        EvidenceSpec(
            base_seed=seed if seed is not None else -1,
            episodes_per_cell=(episodes_per_cell if episodes_per_cell is not None else -1),
            scenarios=tuple(cast(list[str], scenarios)) if scenarios_valid else (),
            operating_points=tuple(value[0] for value in OPERATING_POINT_VALUES),
        ),
    )
    raw_evidence_valid = recomputed is not None
    raw_summaries_match = bool(
        recomputed is not None
        and json_exact_equal(selection_aggregate, cast(JsonValue, recomputed.selection_aggregate))
        and json_exact_equal(sealed_aggregate, cast(JsonValue, recomputed.sealed_aggregate))
        and json_exact_equal(
            selection_comparisons, cast(JsonValue, recomputed.selection_comparisons)
        )
        and json_exact_equal(sealed_comparisons, cast(JsonValue, recomputed.sealed_comparisons))
        and json_exact_equal(
            sealed_cohort.get("byScenarioAndOperatingPoint"),
            cast(JsonValue, recomputed.sealed_by_cell),
        )
        and selected_name == recomputed.selected_policy
    )
    trusted_selection_comparison = (
        recomputed.selection_comparisons.get(selected_name) if recomputed else None
    )
    trusted_sealed_comparison = (
        recomputed.sealed_comparisons.get(selected_name) if recomputed else None
    )
    selection_interval_passed = bool(
        trusted_selection_comparison and _passes_paired_promotion_gate(trusted_selection_comparison)
    )
    sealed_interval_passed = bool(
        trusted_sealed_comparison and _passes_paired_promotion_gate(trusted_sealed_comparison)
    )
    paired_improvement = selection_interval_passed and sealed_interval_passed
    promoted_policy_implemented = runtime_policy_implemented(selected_name)
    runtime_key = (
        selected_name
        if paired_improvement
        and promoted_policy_implemented
        and selected_name in RUNTIME_POLICY_IDS
        else "deployed_runtime"
    )
    expected_runtime_policy = next(
        (
            policy_id
            for policy_name, policy_id in RUNTIME_POLICY_IDS.items()
            if policy_name == runtime_key
        ),
        RUNTIME_POLICY_IDS["deployed_runtime"],
    )
    aggregate_schema_valid = bool(
        expected_paired_count > 0
        and _aggregate_map_valid(selection_aggregate, expected_episodes=expected_paired_count)
        and _aggregate_map_valid(sealed_aggregate, expected_episodes=expected_paired_count)
    )
    paired_schema_valid = bool(
        _paired_comparisons_valid(selection_comparisons)
        and _paired_comparisons_valid(sealed_comparisons)
    )
    safety = cast(dict[str, JsonValue], result["runtimeSafetyContract"])
    runtime_evidence = cast(dict[str, JsonValue], result["runtimeEvidence"])
    deployed_resolved = _finite_float(deployed.get("resolvedWithinBudgetRate"))
    static_resolved = _finite_float(static_baseline.get("resolvedWithinBudgetRate"))
    deployed_top1 = _finite_float(deployed.get("finalTop1Accuracy"))
    static_top1 = _finite_float(static_baseline.get("finalTop1Accuracy"))
    deployed_false_activation = _finite_float(deployed.get("falseZoneActivationRate"))
    deployed_scans = _finite_float(deployed.get("meanScansToResolution"))
    static_scans = _finite_float(static_baseline.get("meanScansToResolution"))
    checks = {
        "result_contract_valid": result_contract_valid,
        "seed_is_strict_integer": seed is not None,
        "replay_contract_valid": replay_contract_valid,
        "public_reid_evidence_path_allowed": public_evidence_path_allowed,
        "public_reid_evidence_source_valid": public_evidence_source_valid,
        "public_reid_evidence_hash_matches": public_evidence_hash_matches,
        "public_reid_evidence_metrics_match": public_evidence_metrics_match,
        "paired_evidence_path_allowed": paired_evidence_path_allowed,
        "paired_evidence_hash_matches_trusted_digest": paired_evidence_hash_matches,
        "paired_evidence_records_valid": raw_evidence_valid,
        "summaries_recomputed_from_paired_evidence": raw_summaries_match,
        "scenario_schema_valid": scenarios_valid,
        "operating_point_schema_valid": operating_points_are_valid,
        "aggregate_metric_schema_valid": aggregate_schema_valid,
        "paired_interval_schema_valid": paired_schema_valid,
        "selected_policy_exists_in_both_cohorts": (
            selected_name in selection_aggregate and selected_name in sealed_aggregate
        ),
        "cohort_contracts_are_closed": (
            set(selection_cohort)
            == {"seedOffset", "aggregateByPolicy", "pairedComparisonsAgainstDeployed"}
            and set(sealed_cohort)
            == {
                "seedOffset",
                "aggregateByPolicy",
                "pairedComparisonsAgainstDeployed",
                "byScenarioAndOperatingPoint",
            }
        ),
        "selection_and_test_are_sealed": (
            _strict_int(selection_cohort.get("seedOffset")) == 0
            and _strict_int(sealed_cohort.get("seedOffset")) == 10_000_000
        ),
        "paired_episode_count_is_sealed_only": (
            _strict_int(result["pairedEpisodeCount"]) == expected_paired_count
        ),
        "deployed_resolution_improved_over_static": (
            aggregate_schema_valid
            and deployed_resolved is not None
            and static_resolved is not None
            and deployed_resolved > static_resolved
        ),
        "deployed_top1_improved_over_static": (
            aggregate_schema_valid
            and deployed_top1 is not None
            and static_top1 is not None
            and deployed_top1 > static_top1
        ),
        "false_activation_within_manual_review_guardrail": (
            aggregate_schema_valid
            and deployed_false_activation is not None
            and deployed_false_activation <= 0.05
            and safety["autoMatchAllowed"] is False
            and safety["operatorReviewRequired"] is True
        ),
        "deployed_mean_scans_improved_over_static": (
            aggregate_schema_valid
            and deployed_scans is not None
            and static_scans is not None
            and deployed_scans < static_scans
        ),
        "selection_paired_interval_decision_matches": (
            promotion["selectionPairedIntervalPassed"] is selection_interval_passed
        ),
        "sealed_paired_interval_decision_matches": (
            promotion["sealedTestPairedIntervalPassed"] is sealed_interval_passed
        ),
        "promotion_decision_matches_paired_intervals": (
            promotion["proxyMaterialImprovementOverDeployedConfirmed"] is paired_improvement
        ),
        "runtime_policy_matches_promotion_decision": (
            result["selectedRuntimePolicy"] == expected_runtime_policy
        ),
        "promoted_policy_has_runtime_implementation": (
            not paired_improvement or promoted_policy_implemented
        ),
        "promotion_claim_contract_is_exact": (
            set(promotion)
            == {
                "projectCctvGeneralization85Confirmed",
                "cameraUtilityCausalImprovementConfirmed",
                "selectionPairedIntervalPassed",
                "sealedTestPairedIntervalPassed",
                "proxyMaterialImprovementOverDeployedConfirmed",
                "reason",
            }
            and promotion.get("reason") == PROMOTION_REASON
        ),
        "selection_metric_contract_is_exact": (
            result.get("selectionMetricOrder")
            == [
                "resolvedWithinBudgetRate descending",
                "falseZoneActivationRate ascending",
                "meanScansToResolution ascending",
            ]
        ),
        "runtime_evidence_contract_is_closed": (
            set(runtime_evidence) == {"execution", "python"}
            and runtime_evidence.get("execution") == "cpu-deterministic-policy-replay"
            and isinstance(runtime_evidence.get("python"), str)
            and re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", cast(str, runtime_evidence.get("python")))
            is not None
        ),
        "safety_contract_is_closed": (
            set(safety)
            == {
                "operatorReviewRequired",
                "autoMatchAllowed",
                "probabilityProvenanceRequired",
                "sameTrackEvidenceDeduplicated",
                "staleProbabilityRevisionRejected",
                "trustedRegistryAllowlistRequired",
                "crossCameraCorrelationGroupRequired",
            }
            and safety.get("sameTrackEvidenceDeduplicated") is True
            and safety.get("crossCameraCorrelationGroupRequired") is True
        ),
        "operator_review_enforced": safety["operatorReviewRequired"] is True,
        "auto_match_disabled": safety["autoMatchAllowed"] is False,
        "provenance_required": safety["probabilityProvenanceRequired"] is True,
        "trusted_registry_required": safety["trustedRegistryAllowlistRequired"] is True,
        "stale_probability_revision_rejected": safety["staleProbabilityRevisionRejected"] is True,
        "project_claim_blocked": (promotion["projectCctvGeneralization85Confirmed"] is False),
        "causal_improvement_claim_blocked": (
            promotion["cameraUtilityCausalImprovementConfirmed"] is False
        ),
        "topology_proxy_claim_enforced": (
            replay["projectCctvEvidence"] is False
            and replay["synchronizedMultiCameraObservation"] is False
        ),
    }
    passed = all(checks.values())
    artifact = {
        "schemaVersion": "autoresearch-mission-result-v1",
        "status": "passed" if passed else "failed",
        "passed": passed,
        "summary": (
            f"selected={selected_name}; checks="
            + ",".join(name for name, value in checks.items() if not value)
        ),
        "checks": checks,
        "outputArtifact": args.result.as_posix(),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n")
    print(json.dumps(artifact, sort_keys=True))
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

