from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .distillation import (
    DistillationDataError,
    read_distillation_samples,
    to_qwen_record,
    write_qwen_jsonl,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="qwen-distill")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("validate", "prepare"):
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--input", type=Path, required=True)
        subparser.add_argument("--image-root", type=Path, required=True)
        subparser.add_argument("--skip-hash", action="store_true")
        if command == "prepare":
            subparser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.skip_hash and os.environ.get("QWEN_ENVIRONMENT") == "production":
            raise DistillationDataError("--skip-hash is disabled in production")
        samples = read_distillation_samples(args.input)
        records = tuple(
            to_qwen_record(sample, args.image_root, verify_hash=not args.skip_hash)
            for sample in samples
        )
        if args.command == "prepare":
            write_qwen_jsonl(records, args.output)
            result = {"records": len(records), "output": str(args.output)}
        else:
            result = {"records": len(records), "status": "valid"}
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
        return 0
    except (DistillationDataError, FileNotFoundError, OSError, ValueError) as error:
        print(f"distillation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
