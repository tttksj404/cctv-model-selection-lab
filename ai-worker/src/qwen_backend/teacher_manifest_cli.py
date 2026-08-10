from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .distillation import write_distillation_jsonl
from .teacher_adapters import TeacherAdapterError, build_teacher_adapter


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="build-geometry-manifest")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        adapter = build_teacher_adapter(args.mode)
        records = adapter.load(args.input)
        write_distillation_jsonl(records, args.output)
        print(json.dumps({"mode": args.mode, "records": len(records)}, separators=(",", ":")))
        return 0
    except (OSError, TeacherAdapterError, ValueError) as error:
        print(f"teacher manifest error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

