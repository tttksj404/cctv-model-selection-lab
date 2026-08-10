from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import ValidationError

from qwen_backend.cctv_promotion_contract import (
    CCTVPromotionMetrics,
    PromotionValidationError,
    TrainingPromotionConfig,
    validate_promotion_metrics,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--metrics", type=Path, required=True)
    parser.add_argument(
        "--config", type=Path, default=Path("training/cctv_attribute_training_v2.json")
    )
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument("--output", type=Path)
    return parser


def _load_json(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise PromotionValidationError(f"cannot read JSON file: {path}") from error


def main() -> int:
    args = _parser().parse_args()
    try:
        metrics = CCTVPromotionMetrics.model_validate_json(_load_json(args.metrics))
        config = TrainingPromotionConfig.model_validate_json(_load_json(args.config))
        report = validate_promotion_metrics(
            metrics,
            config.promotion_gate,
            config.split_policy.local_video_conditions_are_test_only,
            args.workspace,
        )
    except (PromotionValidationError, ValidationError, json.JSONDecodeError) as error:
        reason = "invalid promotion input"
        if isinstance(error, PromotionValidationError):
            reason = str(error)
        elif isinstance(error, ValidationError):
            reason = "invalid promotion input: " + "; ".join(
                f"{'.'.join(str(part) for part in item['loc'])}:{item['type']}"
                for item in error.errors(include_url=False)
            )
        payload = {
            "schema_version": "cctv-promotion-report-v1",
            "status": "blocked",
            "passed": False,
            "reasons": (reason,),
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
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

