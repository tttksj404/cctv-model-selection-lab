from __future__ import annotations

import argparse
import json
import sys
from contextlib import redirect_stdout

from qwen_backend.candidate_runtime import run_runtime
from qwen_backend.solider_clip_engine import EngineConfig, create_engine, cuda_available


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the EyesOnU GPU candidate model contract over stdin/stdout.",
    )
    parser.add_argument(
        "--health",
        action="store_true",
        help="Validate static model configuration without loading GPU weights.",
    )
    return parser


def _health() -> int:
    config = EngineConfig.from_environment()
    reasons: list[str] = []
    if config.device == "cuda" and not cuda_available():
        reasons.append("cuda_unavailable")
    if config.reid_checkpoint is None:
        reasons.append("reid_checkpoint_not_configured")
    elif not config.reid_checkpoint.is_file():
        reasons.append("reid_checkpoint_missing")
    if config.solider_root is None:
        reasons.append("solider_root_not_configured")
    elif not config.solider_root.is_dir():
        reasons.append("solider_root_missing")
    payload = {
        "schemaVersion": "eyesonu-candidate-runtime-health-v1",
        "modelKey": config.model_key,
        "ready": not reasons,
        "reasons": reasons,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=False))
    return 0 if not reasons else 2


def main() -> int:
    args = _parser().parse_args()
    if args.health:
        return _health()
    try:
        raw_request = sys.stdin.read()
        with redirect_stdout(sys.stderr):
            response = run_runtime(raw_request, create_engine())
        sys.stdout.write(response)
    except (FileNotFoundError, ImportError, OSError, RuntimeError, ValueError) as exception:
        message = " ".join(str(exception).split())[:500] or type(exception).__name__
        sys.stderr.write(f"candidate_runtime_failed: {message}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
