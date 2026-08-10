from __future__ import annotations

import argparse
import json
from pathlib import Path

FIELDS = ("upper_color", "lower_color", "carrying", "headwear", "visibility")


def _read(path: Path) -> dict[str, dict[str, str]]:
    rows = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["trackId"]] = row
    return rows


def _f1(gold: list[str], predicted: list[str]) -> float:
    labels = sorted(set(gold) | set(predicted))
    values = []
    for label in labels:
        tp = sum(
            actual == label and guess == label
            for actual, guess in zip(gold, predicted, strict=True)
        )
        fp = sum(
            actual != label and guess == label
            for actual, guess in zip(gold, predicted, strict=True)
        )
        fn = sum(
            actual == label and guess != label
            for actual, guess in zip(gold, predicted, strict=True)
        )
        denominator = 2 * tp + fp + fn
        values.append(2 * tp / denominator if denominator else 0.0)
    return sum(values) / len(values) if values else 0.0


def score(adjudication_path: Path, prediction_path: Path, output: Path) -> dict[str, object]:
    gold_rows = _read(adjudication_path)
    prediction_rows = _read(prediction_path)
    field_metrics: dict[str, dict[str, float | int]] = {}
    exact_slots = 0
    slot_count = 0
    instance_exact = 0
    evaluated_instances = 0
    for field in FIELDS:
        gold: list[str] = []
        predicted: list[str] = []
        for track_id, row in gold_rows.items():
            value = row["adjudicatedAttributes"][field]
            if value == "unknown" or track_id not in prediction_rows:
                continue
            guess = prediction_rows[track_id]["attributes"][field]["label"]
            gold.append(value)
            predicted.append(guess)
        matches = sum(actual == guess for actual, guess in zip(gold, predicted, strict=True))
        exact_slots += matches
        slot_count += len(gold)
        field_metrics[field] = {
            "count": len(gold),
            "accuracy": matches / len(gold) if gold else 0.0,
            "macro_f1": _f1(gold, predicted),
        }
    for track_id, row in gold_rows.items():
        labels = [row["adjudicatedAttributes"][field] for field in FIELDS]
        if track_id not in prediction_rows or not any(value != "unknown" for value in labels):
            continue
        evaluated_instances += 1
        guesses = [prediction_rows[track_id]["attributes"][field]["label"] for field in FIELDS]
        if all(
            value == "unknown" or value == guess
            for value, guess in zip(labels, guesses, strict=True)
        ):
            instance_exact += 1
    result = {
        "schemaVersion": "cctv-attribute-adjudication-v1",
        "adjudication": "manual contact-sheet review; unknown fields excluded from accuracy",
        "metrics": {
            "test": {
                "track_exact_match": instance_exact / evaluated_instances
                if evaluated_instances
                else 0.0,
                "mA": exact_slots / slot_count if slot_count else 0.0,
                "InsF1": sum(item["macro_f1"] for item in field_metrics.values()) / len(FIELDS),
            }
        },
        "evaluatedInstances": evaluated_instances,
        "evaluatedAttributeSlots": slot_count,
        "fieldMetrics": field_metrics,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--adjudication", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(score(args.adjudication, args.predictions, args.output), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

