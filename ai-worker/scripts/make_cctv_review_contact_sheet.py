from __future__ import annotations

import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _quality(row: dict[str, object]) -> float:
    value = row.get("quality")
    return float(value) if isinstance(value, int | float) else 0.0


def _label(row: dict[str, object]) -> str:
    track_id = str(row["trackId"])
    identity = row.get("identityGroupId")
    target_role = row.get("targetRole")
    if target_role is not None or identity is not None:
        return f"{target_role or 'unknown'}\n{identity or 'unassigned'}\n{track_id}"
    return f"{track_id}\nq={_quality(row):.3f}"


def build_contact_sheet(root: Path, manifest: Path, output: Path) -> int:
    rows = [
        json.loads(line)
        for line in manifest.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    representatives: dict[str, dict[str, object]] = {}
    for row in rows:
        track_id = str(row["trackId"])
        current = representatives.get(track_id)
        if current is None or _quality(row) > _quality(current):
            representatives[track_id] = row
    thumb_width, thumb_height = 160, 220
    cell_width, cell_height, columns = 240, 275, 5
    sheet = Image.new(
        "RGB",
        (columns * cell_width, ((len(representatives) + columns - 1) // columns) * cell_height),
        "white",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    for index, row in enumerate(
        representatives[track_id] for track_id in sorted(representatives)
    ):
        with Image.open(root / str(row["framePath"])) as source:
            image = source.convert("RGB")
        image.thumbnail((thumb_width, thumb_height))
        x = index % columns * cell_width + (cell_width - image.width) // 2
        y = index // columns * cell_height + 4
        sheet.paste(image, (x, y))
        draw.multiline_text(
            (index % columns * cell_width + 4, index // columns * cell_height + 226),
            _label(row),
            fill="black",
            font=font,
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, quality=92)
    return len(representatives)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    print(build_contact_sheet(arguments.root, arguments.manifest, arguments.output))

