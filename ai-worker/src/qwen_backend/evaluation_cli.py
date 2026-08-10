from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .evaluation import evaluate_files, write_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qwen-evaluate")
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--prediction", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    try:
        report = evaluate_files(args.reference, args.prediction)
        if args.output:
            write_report(report, args.output)
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":")))
        return 0
    except (OSError, ValueError) as error:
        print(f"evaluation error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

