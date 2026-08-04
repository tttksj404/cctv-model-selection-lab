import json
from pathlib import Path

from PIL import Image

from scripts.make_cctv_review_contact_sheet import build_contact_sheet


def test_build_contact_sheet_when_multitrack_rows_have_no_review_labels(tmp_path: Path) -> None:
    # Given
    image_paths = (tmp_path / "one.jpg", tmp_path / "two.jpg")
    for index, image_path in enumerate(image_paths):
        Image.new("RGB", (64, 128), color=(index * 80, 20, 30)).save(image_path)
    rows = (
        {"trackId": "video-track-0001", "framePath": "one.jpg", "quality": 0.7},
        {"trackId": "video-track-0002", "framePath": "two.jpg", "quality": 0.9},
    )
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(
        "".join(f"{json.dumps(row)}\n" for row in rows),
        encoding="utf-8",
    )
    output = tmp_path / "sheet.jpg"

    # When
    track_count = build_contact_sheet(tmp_path, manifest, output)

    # Then
    assert track_count == 2
    assert output.is_file()
