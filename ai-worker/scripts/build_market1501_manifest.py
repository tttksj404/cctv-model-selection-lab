import argparse
import json
from pathlib import Path

from fetch_market1501_subset import row_for


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [
        row_for(
            path.relative_to(args.root).as_posix(),
            path,
            args.root,
        )
        for path in args.root.rglob("*.jpg")
        if path.is_file()
    ]
    rows.sort(key=lambda row: str(row["sourcePath"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
