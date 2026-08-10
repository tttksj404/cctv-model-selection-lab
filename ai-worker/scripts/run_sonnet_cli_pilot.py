#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from qwen_backend.sonnet_cli import (
    ClaudeAuthStatus,
    SonnetCLIConfig,
    SonnetCLIError,
    inspect_auth_status,
    resolve_claude_executable,
    run_structured_teacher,
)

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


PROJECT_ROOT = Path(__file__).resolve().parents[1]
IMAGE_DIR = PROJECT_ROOT / "experiments/data/cctv_proxy/person_only/simuletic"
METADATA_PATH = IMAGE_DIR / "metadata.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "experiments/results/sonnet_cli_pilot_20260728.json"
FIELDS = (
    "gender",
    "age_group",
    "hair_color",
    "viewpoint",
    "top_color",
    "top_type",
    "bottom_color",
    "bottom_type",
    "accessory",
)
STABLE_FIELDS = tuple(field for field in FIELDS if field != "viewpoint")
SCHEMA: dict[str, JsonValue] = {
    "type": "object",
    "properties": {
        "gender": {"type": ["string", "null"]},
        "age_group": {"type": ["string", "null"]},
        "hair_color": {"type": ["string", "null"]},
        "viewpoint": {"type": ["string", "null"]},
        "top_color": {"type": ["string", "null"]},
        "top_type": {"type": ["string", "null"]},
        "bottom_color": {"type": ["string", "null"]},
        "bottom_type": {"type": ["string", "null"]},
        "footwear": {"type": ["string", "null"]},
        "accessory": {"type": ["string", "null"]},
        "visibility": {"type": ["string", "null"]},
        "teacher_confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": [
        "gender",
        "age_group",
        "hair_color",
        "viewpoint",
        "top_color",
        "top_type",
        "bottom_color",
        "bottom_type",
        "footwear",
        "accessory",
        "visibility",
        "teacher_confidence",
    ],
    "additionalProperties": False,
}


def json_object(raw: str) -> dict[str, JsonValue]:
    loaded: JsonValue = json.loads(raw)
    if not isinstance(loaded, dict):
        raise ValueError("expected a JSON object")
    result: dict[str, JsonValue] = {}
    for key, raw_value in loaded.items():
        if raw_value is None or isinstance(raw_value, (str, int, float, bool)):
            result[key] = raw_value
            continue
        if isinstance(raw_value, dict):
            nested: dict[str, JsonValue] = {}
            for nested_key, nested_value in raw_value.items():
                if nested_value is None or isinstance(
                    nested_value, (str, int, float, bool)
                ):
                    nested[nested_key] = nested_value
                    continue
                raise ValueError("unsupported nested JSON value")
            result[key] = nested
            continue
        raise ValueError("unsupported JSON value")
    return result


def string_value(value: JsonValue) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def load_metadata() -> dict[str, dict[str, str]]:
    records: dict[str, dict[str, str]] = {}
    key_map = {"age": "age_group", "hair": "hair_color", "angle": "viewpoint"}
    for line in METADATA_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json_object(line)
        image = string_value(record.get("image"))
        attrs = record.get("attributes")
        if image is None or not isinstance(attrs, dict):
            continue
        records[image] = {
            key_map.get(key, key): value
            for key, raw_value in attrs.items()
            if (value := string_value(raw_value)) is not None
        }
    return records


def canonical(field: str, value: str | None) -> str | None:
    if value is None:
        return None
    text = " ".join(value.lower().replace("_", " ").split())
    if field == "gender":
        return {"woman": "female", "man": "male"}.get(text, text)
    if field == "age_group":
        if "middle" in text or "adult" in text:
            return "adult"
        if "elder" in text or "senior" in text:
            return "elderly"
        return text
    if field == "viewpoint":
        if "back" in text:
            return "back"
        if "rear" in text:
            return "back"
        if "side" in text or "profile" in text:
            return "side"
        if "front" in text:
            return "front"
        return text
    if field == "accessory":
        if "sunglass" in text:
            return "sunglasses"
        if text in {"none", "nothing", "no accessory"}:
            return None
    return text


def equivalent(field: str, target: str | None, prediction: str | None) -> bool:
    target_c = canonical(field, target)
    prediction_c = canonical(field, prediction)
    if target_c is None:
        return prediction_c is None
    if prediction_c is None:
        return False
    if field in {"top_type", "bottom_type"}:
        return target_c in prediction_c or prediction_c in target_c
    return target_c == prediction_c


def run_teacher(
    image_path: Path,
    config: SonnetCLIConfig,
) -> tuple[dict[str, JsonValue] | None, str | None]:
    prompt = (
        f"Read the local image file {image_path} with the Read tool. "
        "This is a CCTV person-attribute teacher-label pilot. Inspect only visible "
        "evidence, use null when an attribute is not visible, do not infer identity, "
        "and return only the requested JSON object."
    )
    try:
        result = run_structured_teacher(
            config,
            prompt=prompt,
            schema=SCHEMA,
            working_directory=PROJECT_ROOT,
        )
        return result.structured_output, None
    except SonnetCLIError as exc:
        return None, str(exc)


def evaluate(target: dict[str, str], prediction: dict[str, JsonValue]) -> dict[str, JsonValue]:
    normalized_prediction: dict[str, str | None] = {
        field: string_value(prediction.get(field)) for field in FIELDS
    }
    field_scores: dict[str, JsonValue] = {
        field: equivalent(field, target.get(field), normalized_prediction[field])
        for field in FIELDS
        if field in target
    }
    stable_field_scores: dict[str, JsonValue] = {
        field: score for field, score in field_scores.items() if field in STABLE_FIELDS
    }
    matched_fields = sum(
        int(score) for score in field_scores.values() if isinstance(score, bool)
    )
    stable_matched_fields = sum(
        int(score) for score in stable_field_scores.values() if isinstance(score, bool)
    )
    return {
        "field_scores": field_scores,
        "matched_fields": matched_fields,
        "measured_fields": len(field_scores),
        "exact_record_match": bool(field_scores)
        and all(score is True for score in field_scores.values()),
        "stable_field_scores": stable_field_scores,
        "stable_matched_fields": stable_matched_fields,
        "stable_measured_fields": len(stable_field_scores),
        "exact_stable_record_match": bool(stable_field_scores)
        and all(score is True for score in stable_field_scores.values()),
    }


def image_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_result(
    limit: int,
    config: SonnetCLIConfig,
    auth_status: ClaudeAuthStatus,
) -> dict[str, JsonValue]:
    metadata = load_metadata()
    image_paths = sorted(IMAGE_DIR.glob("*.png"))[:limit]
    samples: list[JsonValue] = []
    for image_path in image_paths:
        prediction, error = run_teacher(image_path.resolve(), config)
        target = metadata.get(image_path.name, {})
        target_json: dict[str, JsonValue] = {
            key: value for key, value in target.items()
        }
        sample: dict[str, JsonValue] = {
            "image": image_path.name,
            "sha256": image_sha256(image_path),
            "target": target_json,
            "prediction": prediction,
            "error": error,
        }
        if prediction is not None and target:
            sample["evaluation"] = evaluate(target, prediction)
        samples.append(sample)

    field_totals: dict[str, list[int]] = {field: [0, 0] for field in FIELDS}
    stable_field_totals: dict[str, list[int]] = {
        field: [0, 0] for field in STABLE_FIELDS
    }
    exact_matches = 0
    exact_stable_matches = 0
    evaluated = 0
    for sample_value in samples:
        if not isinstance(sample_value, dict):
            continue
        sample = sample_value
        evaluation = sample.get("evaluation")
        if not isinstance(evaluation, dict):
            continue
        evaluated += 1
        if evaluation.get("exact_record_match") is True:
            exact_matches += 1
        if evaluation.get("exact_stable_record_match") is True:
            exact_stable_matches += 1
        field_scores = evaluation.get("field_scores")
        if isinstance(field_scores, dict):
            for field, score in field_scores.items():
                if field in field_totals and isinstance(score, bool):
                    field_totals[field][1] += 1
                    field_totals[field][0] += int(score)
        stable_field_scores = evaluation.get("stable_field_scores")
        if isinstance(stable_field_scores, dict):
            for field, score in stable_field_scores.items():
                if field in stable_field_totals and isinstance(score, bool):
                    stable_field_totals[field][1] += 1
                    stable_field_totals[field][0] += int(score)
    field_accuracy: dict[str, JsonValue] = {
        field: (hits / total if total else None)
        for field, (hits, total) in field_totals.items()
    }
    stable_field_accuracy: dict[str, JsonValue] = {
        field: (hits / total if total else None)
        for field, (hits, total) in stable_field_totals.items()
    }
    metrics: dict[str, JsonValue] = {
        "evaluated_samples": evaluated,
        "exact_record_accuracy": exact_matches / evaluated if evaluated else None,
        "exact_stable_record_accuracy": (
            exact_stable_matches / evaluated if evaluated else None
        ),
        "field_accuracy": field_accuracy,
        "stable_field_accuracy": stable_field_accuracy,
        "status": "measured" if evaluated else "blocked",
        "scope_warning": "Synthetic CCTV proxy metadata, not real identity/track-heldout CCTV.",
    }
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "teacher_model_requested": config.model,
        "teacher_transport": "claude_cli_oauth",
        "auth": {
            "logged_in": auth_status.logged_in,
            "auth_method": auth_status.auth_method,
            "api_provider": auth_status.api_provider,
            "subscription_type": auth_status.subscription_type,
        },
        "dataset": "cctv_proxy/person_only/simuletic",
        "sample_limit": limit,
        "metrics": metrics,
        "samples": samples,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--claude-bin", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--preflight-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.limit < 1:
        raise SystemExit("--limit must be at least 1")
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be at least 1")
    executable = resolve_claude_executable(args.claude_bin)
    config = SonnetCLIConfig(
        executable=executable,
        model=args.model,
        timeout_seconds=args.timeout_seconds,
    )
    auth_status = inspect_auth_status(config)
    if args.preflight_only:
        print(
            json.dumps(
                {
                    "ready": True,
                    "model": config.model,
                    "auth_method": auth_status.auth_method,
                    "api_provider": auth_status.api_provider,
                    "subscription_type": auth_status.subscription_type,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 0
    result = build_result(args.limit, config, auth_status)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result["metrics"], ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

