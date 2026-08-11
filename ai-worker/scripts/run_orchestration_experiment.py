from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from qwen_backend.orchestration_experiment import PairScoreRow, run_experiment


def _load_rows(path: Path) -> tuple[PairScoreRow, ...]:
    rows: list[PairScoreRow] = []
    with path.open(encoding="utf-8") as source:
        for line_number, line in enumerate(source, start=1):
            if not line.strip():
                continue
            try:
                rows.append(PairScoreRow.model_validate_json(line))
            except ValueError as exc:
                raise ValueError(f"invalid evidence at line {line_number}: {exc}") from exc
    return tuple(rows)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a validation-only fusion loop and a sealed test evaluation."
    )
    parser.add_argument("--manifest", type=Path, required=True, help="pair-evidence JSONL")
    parser.add_argument("--output", type=Path, required=True, help="result JSON path")
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument("--min-known", type=int, default=100)
    parser.add_argument("--min-distractors", type=int, default=100)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.manifest.is_file():
        raise FileNotFoundError(args.manifest)
    rows = _load_rows(args.manifest)
    result = run_experiment(
        rows,
        rounds=args.rounds,
        required_known_queries=args.min_known,
        required_distractor_queries=args.min_distractors,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(result.model_dump_json(indent=2), encoding="utf-8")
    test_recall = result.selected_test.known_recall_at5 if result.selected_test else "n/a"
    print(
        f"status={result.status} selected={result.selected_arm} "
        f"test_recall_at5={test_recall} gate_passed={result.promotion_gate.passed}"
    )
    return 0 if result.status == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
