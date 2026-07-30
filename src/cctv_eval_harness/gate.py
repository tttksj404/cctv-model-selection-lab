from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _artifact_reason(reference: Any, workspace: Path) -> str | None:
    if not isinstance(reference, dict):
        return "artifact reference is not an object"
    path_value = reference.get("path")
    digest = reference.get("sha256")
    if not isinstance(path_value, str) or not isinstance(digest, str):
        return "artifact path or SHA-256 is missing"
    candidate = Path(path_value)
    if candidate.is_absolute() or ".." in candidate.parts:
        return f"artifact path escapes workspace: {path_value}"
    resolved_workspace = workspace.resolve()
    resolved = (resolved_workspace / candidate).resolve()
    if resolved_workspace not in resolved.parents or not resolved.is_file():
        return f"artifact is missing: {path_value}"
    actual = hashlib.sha256(resolved.read_bytes()).hexdigest()
    if actual != digest.lower():
        return f"artifact hash does not match: {path_value}"
    return None


def evaluate(payload: dict[str, Any], policy: dict[str, Any], workspace: Path) -> dict[str, Any]:
    reasons: list[str] = []
    if payload.get("schemaVersion") != "cctv-candidate-evaluation-v1":
        reasons.append("unsupported evaluation schema")
    if payload.get("measurementScope") != "sealed_identity_track_heldout":
        reasons.append("measurement is not a sealed identity and track-heldout evaluation")
    if payload.get("identityLabelsAvailable") is not True:
        reasons.append("independent identity labels are unavailable")
    if payload.get("trackHeldoutEligible") is not True:
        reasons.append("track-heldout metrics are not eligible")
    if payload.get("humanReviewComplete") is not True:
        reasons.append("human review is incomplete")

    references = payload.get("artifactRefs")
    if not isinstance(references, list) or not references:
        reasons.append("manifest and evaluation evidence references are missing")
    else:
        for reference in references:
            reason = _artifact_reason(reference, workspace)
            if reason is not None:
                reasons.append(reason)

    thresholds = policy.get("thresholds")
    metrics = payload.get("metrics")
    if not isinstance(thresholds, dict) or not isinstance(metrics, dict):
        reasons.append("thresholds or metrics are missing")
    else:
        for key in ("attributeMacroF1", "identityRank1", "identityRecallAt5"):
            metric = _number(metrics.get(key))
            threshold = _number(thresholds.get(key))
            if metric is None or threshold is None:
                reasons.append(f"{key} is missing")
            elif metric < threshold:
                reasons.append(f"{key} is below threshold")
        false_match = _number(metrics.get("falseMatchRate"))
        maximum_false_match = _number(thresholds.get("falseMatchRateMaximum"))
        if false_match is None or maximum_false_match is None:
            reasons.append("falseMatchRate is missing")
        elif false_match > maximum_false_match:
            reasons.append("falseMatchRate is above threshold")

    approved = not reasons
    return {
        "schemaVersion": "cctv-candidate-promotion-report-v1",
        "candidate": payload.get("candidate", "unknown"),
        "status": "APPROVED" if approved else "NOT_APPROVED",
        "reasons": reasons,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a candidate-model promotion record.")
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    try:
        report = evaluate(_read_json(args.input), _read_json(args.config), args.workspace)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        report = {"status": "NOT_APPROVED", "reasons": [str(error)]}

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    return 0 if report["status"] == "APPROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())

