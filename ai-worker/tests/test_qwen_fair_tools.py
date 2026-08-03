import json
import sys
from pathlib import Path

import pytest

from scripts.prepare_qwen_fair_dataset import main as prepare_main
from scripts.score_qwen_fair_results import _reference
from scripts.score_qwen_fair_results import main as score_main


def _labels() -> dict[str, int]:
    return {
        "Female": 0,
        "AgeOver60": 0,
        "AgeLess18": 0,
        "Front": 1,
        "Side": 0,
        "HandBag": 0,
        "ShoulderBag": 0,
        "Backpack": 0,
        "ShortSleeve": 1,
        "LongSleeve": 0,
        "Trousers": 1,
        "Shorts": 0,
        "SkirtDress": 0,
    }


def _reference_row() -> dict[str, object]:
    return {
        "messages": [
            {
                "role": "assistant",
                "content": json.dumps(
                    {
                        "attributes": {
                            "gender": "male",
                            "age": "adult",
                            "viewpoint": "front",
                            "accessory": "none",
                            "sleeve": "short",
                            "bottom_type": "trousers",
                        }
                    }
                ),
            }
        ]
    }


def test_reference_rejects_missing_field() -> None:
    row = _reference_row()
    payload = json.loads(row["messages"][0]["content"])
    del payload["attributes"]["bottom_type"]
    row["messages"][0]["content"] = json.dumps(payload)
    with pytest.raises(ValueError, match="exactly the six fields"):
        _reference(row)


def test_score_rejects_empty_reference(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    reference = tmp_path / "reference.jsonl"
    prediction = tmp_path / "prediction.jsonl"
    output = tmp_path / "result.json"
    reference.write_text("", encoding="utf-8")
    prediction.write_text("", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_qwen_fair_results.py",
            "--reference",
            str(reference),
            "--prediction",
            str(prediction),
            "--output",
            str(output),
            "--model",
            "test",
            "--method",
            "base",
        ],
    )
    with pytest.raises(SystemExit, match="reference dataset is empty"):
        score_main()


def test_score_writes_provenance_for_valid_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference = tmp_path / "reference.jsonl"
    prediction = tmp_path / "prediction.jsonl"
    output = tmp_path / "result.json"
    reference.write_text(json.dumps(_reference_row()) + "\n", encoding="utf-8")
    prediction.write_text(
        json.dumps({"response": _reference_row()["messages"][0]["content"]}) + "\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "score_qwen_fair_results.py",
            "--reference",
            str(reference),
            "--prediction",
            str(prediction),
            "--output",
            str(output),
            "--model",
            "test",
            "--method",
            "base",
        ],
    )
    assert score_main() == 0
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["fieldAccuracyPct"] == 100.0
    assert len(report["referenceSha256"]) == 64
    assert len(report["predictionSha256"]) == 64


def test_prepare_rejects_image_outside_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_root = tmp_path / "images"
    image_root.mkdir()
    outside = tmp_path / "outside.jpg"
    outside.write_bytes(b"not-an-image")
    manifest = tmp_path / "manifest.jsonl"
    rows = [
        {"image_name": "../outside.jpg", "labels": _labels()},
        *[{"image_name": f"image-{index}.jpg", "labels": _labels()} for index in range(11)],
    ]
    for index in range(11):
        (image_root / f"image-{index}.jpg").write_bytes(b"not-an-image")
    manifest.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "prepare_qwen_fair_dataset.py",
            "--source-manifest",
            str(manifest),
            "--image-root",
            str(image_root),
            "--output-dir",
            str(tmp_path / "output"),
            "--limit",
            "12",
        ],
    )
    with pytest.raises(SystemExit, match="outside image root"):
        prepare_main()
