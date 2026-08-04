from __future__ import annotations

import argparse
import json
from pathlib import Path

from qwen_backend.cctv_training_contract import (
    TrainingManifestError,
    load_training_manifest,
    validate_training_manifest,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    parser.add_argument("--max-errors", type=int, default=20)
    parser.add_argument("--temporal-embargo-ms", type=int, default=30000)
    parser.add_argument(
        "--condition-holdout",
        action="append",
        default=["landscape_room=test_landscape", "portrait_fisheye=test_portrait_fisheye"],
    )
    return parser


def _parse_holdouts(values: list[str]) -> dict[str, str]:
    holdouts: dict[str, str] = {}
    for value in values:
        condition, separator, split = value.partition("=")
        if not separator or not condition or not split:
            raise TrainingManifestError(f"invalid condition holdout: {value}")
        holdouts[condition] = split
    return holdouts


def main() -> int:
    args = _parser().parse_args()
    try:
        samples = load_training_manifest(args.input_manifest)
        report = validate_training_manifest(
            samples,
            condition_holdouts=_parse_holdouts(args.condition_holdout),
            max_errors=args.max_errors,
            temporal_embargo_ms=args.temporal_embargo_ms,
            workspace=args.workspace,
        )
    except TrainingManifestError as error:
        payload = {
            "schemaVersion": "cctv-attribute-training-report-v1",
            "status": "blocked",
            "error": str(error),
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    payload = report.model_dump(mode="json")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = args.output.with_suffix(".tmp.json")
        temporary_output.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        temporary_output.replace(args.output)
    return 0 if report.status == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
