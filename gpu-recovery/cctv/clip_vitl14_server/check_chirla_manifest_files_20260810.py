from __future__ import annotations

# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///

import argparse
import json
from pathlib import Path


def main() -> None:
    """Report manifest rows whose image is absent from a dataset root."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifests", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    seen: set[str] = set()
    missing: list[str] = []
    total = 0
    for manifest in args.manifests:
        for line in manifest.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            relative = str(row["localPath"])
            if relative in seen:
                continue
            seen.add(relative)
            total += 1
            if not (args.root / relative).is_file():
                missing.append(relative)
    result = {"total": total, "missing": len(missing), "paths": missing}
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"total": total, "missing": len(missing)}, sort_keys=True))
    print("\n".join(missing))


if __name__ == "__main__":
    main()
