from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import cast

from qwen_backend.cctv_identity_evaluation import CCTVDataError, evaluate_identity_predictions
from qwen_backend.cctv_manifest_io import (
    identity_label_sha256,
    load_track_predictions,
    load_track_references,
    manifest_sha256,
)


def _mapping(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _attribute_metrics(path: Path) -> dict[str, float | None]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    metrics = _mapping(_mapping(payload).get("metrics"))
    test_metrics = _mapping(metrics.get("test"))
    return {name: _number(test_metrics.get(name)) for name in ("track_exact_match", "mA", "InsF1")}


def build_result(
    manifest: Path,
    predictions: Path,
    attribute_result: Path,
    model_name: str,
) -> dict[str, object]:
    references = load_track_references(manifest)
    ranked_predictions = load_track_predictions(predictions)
    report = evaluate_identity_predictions(
        references,
        ranked_predictions,
        model_name=model_name,
    )
    attributes = _attribute_metrics(attribute_result)
    attribute_complete = all(value is not None for value in attributes.values())
    identity_labels_available = report.status != "blocked_missing_identity_labels"
    identity_valid = report.status == "valid"
    local_pilot_only = report.gallery_identity_count < 10
    identity_gate = (
        report.rank1 is not None
        and report.rank1 >= 0.85
        and report.recall_at_5 is not None
        and report.recall_at_5 >= 0.95
        and report.false_match_rate is not None
        and report.false_match_rate <= 0.05
        and report.false_reject_rate is not None
        and report.false_reject_rate <= 0.10
    )
    attribute_gate = (
        attributes["track_exact_match"] is not None
        and attributes["track_exact_match"] >= 0.85
        and attributes["mA"] is not None
        and attributes["mA"] >= 0.85
        and attributes["InsF1"] is not None
        and attributes["InsF1"] >= 0.90
    )
    general85_passed = identity_gate and attribute_gate and not local_pilot_only
    test_metrics = {
        "top1_accuracy": report.rank1,
        "track_exact_match": attributes["track_exact_match"],
        "mA": attributes["mA"],
        "InsF1": attributes["InsF1"],
    }
    return {
        "measurementStatus": {
            "valid": "identity_measured_sealed_test",
            "blocked_missing_gallery": "blocked_missing_gallery",
            "blocked_missing_identity_labels": "blocked_missing_reviewed_identity_labels",
        }[report.status],
        "measurementScope": "local_identity_pilot" if local_pilot_only else "project_candidate",
        "promotionEligible": general85_passed,
        "general85Gate": {
            "passed": general85_passed,
            "identityGatePassed": identity_gate,
            "attributeGatePassed": attribute_gate,
            "minimumGalleryIdentities": 10,
        },
        "evaluationEligibility": {
            "identityLabelsAvailable": identity_labels_available,
            "trackHeldoutMetricsEligible": identity_valid
            and attribute_complete
            and not local_pilot_only,
            "proxyMetricsReusedAsIdentity": False,
        },
        "provenance": {
            "sealedTestManifestSha256": manifest_sha256(manifest),
            "identityLabelSha256": identity_label_sha256(references),
            "splitMethod": "identity_group_and_track_heldout",
            "metricImplementation": "cctv_identity_evaluation_v1",
            "manifestPath": str(manifest),
            "predictionPath": str(predictions),
            "attributeResultPath": str(attribute_result),
        },
        "metrics": {"test": test_metrics},
        "identityReport": report.model_dump(by_alias=True),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--attribute-result", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_result(
            args.manifest,
            args.predictions,
            args.attribute_result,
            args.model_name,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    except (CCTVDataError, OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: cannot build CCTV identity result: {exc}")
        return 1
    print(f"WROTE: {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

