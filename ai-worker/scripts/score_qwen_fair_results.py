from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Final

FIELDS: Final[tuple[str, ...]] = (
    "gender",
    "age",
    "viewpoint",
    "accessory",
    "sleeve",
    "bottom_type",
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--method", choices=("base", "lora"), required=True)
    return parser.parse_args()


def _text(value: object) -> str:
    return value if isinstance(value, str) else ""


def _reference(row: dict[str, object]) -> dict[str, str]:
    if not isinstance(row, dict):
        raise ValueError("reference row must be an object")
    messages = row.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("reference row has no messages")
    last = messages[-1]
    if not isinstance(last, dict):
        raise ValueError("reference assistant message must be an object")
    content = _text(last.get("content"))
    try:
        payload = json.loads(content)
    except json.JSONDecodeError as exc:
        raise ValueError("reference assistant content is not JSON") from exc
    attrs = payload.get("attributes") if isinstance(payload, dict) else None
    if not isinstance(attrs, dict) or set(attrs) != set(FIELDS):
        raise ValueError("reference attributes must contain exactly the six fields")
    if any(not isinstance(attrs[field], str) for field in FIELDS):
        raise ValueError("reference attributes must be strings")
    return {field: attrs[field] for field in FIELDS}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _prediction_text(row: object) -> str:
    if not isinstance(row, dict):
        return ""
    for key in ("response", "predict", "prediction", "output", "generated_text"):
        value = row.get(key)
        if isinstance(value, str):
            return value
    choices = row.get("choices")
    if isinstance(choices, list) and choices and isinstance(choices[0], dict):
        message = choices[0].get("message")
        if isinstance(message, dict) and isinstance(message.get("content"), str):
            return message["content"]
    return ""


def _json_from_text(text: str) -> dict[str, object] | None:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.DOTALL | re.IGNORECASE)
    candidates = [fenced.group(1)] if fenced else []
    candidates.append(cleaned)
    start = cleaned.find("{")
    if start >= 0:
        candidates.append(cleaned[start:])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            attrs = value.get("attributes")
            return attrs if isinstance(attrs, dict) else value
    return None


def main() -> int:
    args = _parse_args()
    references = [
        json.loads(line)
        for line in args.reference.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    predictions = [
        json.loads(line)
        for line in args.prediction.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if not references:
        raise SystemExit("reference dataset is empty")
    if len(references) != len(predictions):
        raise SystemExit(
            f"prediction count {len(predictions)} != reference count {len(references)}"
        )
    correct = {field: 0 for field in FIELDS}
    totals = {field: 0 for field in FIELDS}
    exact = 0
    valid = 0
    for index, (reference_row, prediction_row) in enumerate(
        zip(references, predictions, strict=True), start=1
    ):
        try:
            target = _reference(reference_row)
        except ValueError as exc:
            raise SystemExit(f"invalid reference row {index}: {exc}") from exc
        prediction = _json_from_text(_prediction_text(prediction_row))
        if prediction is not None:
            valid += 1
        prediction = prediction or {}
        row_exact = True
        for field in FIELDS:
            expected = str(target.get(field, ""))
            actual = str(prediction.get(field, ""))
            totals[field] += 1
            if actual == expected:
                correct[field] += 1
            else:
                row_exact = False
        exact += int(row_exact)
    field_accuracy = sum(correct.values()) / max(1, sum(totals.values()))
    report = {
        "schema": "qwen-fair-score-v1",
        "status": "valid",
        "model": args.model,
        "method": args.method,
        "examples": len(references),
        "fields": list(FIELDS),
        "fieldAccuracyPct": field_accuracy * 100,
        "exactMatchPct": exact / max(1, len(references)) * 100,
        "validJsonPct": valid / max(1, len(references)) * 100,
        "perFieldAccuracyPct": {
            field: correct[field] / max(1, totals[field]) * 100 for field in FIELDS
        },
        "reference": str(args.reference.resolve()),
        "prediction": str(args.prediction.resolve()),
        "referenceSha256": _digest(args.reference),
        "predictionSha256": _digest(args.prediction),
        "evaluationContract": "qwen-fair-pa100k-v1/test/six-fields",
        "proxyWarning": (
            "This is not CCTV identity accuracy and does not measure colour or texture."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

