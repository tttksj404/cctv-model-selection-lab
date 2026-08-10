from __future__ import annotations

import json
from pathlib import Path

from scripts.prepare_chirla_cctv_review import build_review_manifest


def test_build_review_manifest_writes_track_contract(tmp_path: Path) -> None:
    root = tmp_path / "chirla"
    root.mkdir()
    rows: list[dict[str, str]] = []
    for identity in ("1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14"):
        for role, split in (("gallery", "gallery"), ("query", "query")):
            path = root / f"{role}_{identity}.png"
            path.write_bytes(b"fake")
            rows.append(
                {
                    "benchmarkRole": role,
                    "cameraId": "camera_1",
                    "identityGroupId": identity,
                    "localPath": path.name,
                    "sequenceId": "seq_001",
                    "sha256": "abc",
                    "subset": split,
                }
            )
    for identity in ("-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11"):
        path = root / f"query_{identity}.png"
        path.write_bytes(b"fake")
        rows.append(
            {
                "benchmarkRole": "query",
                "cameraId": "camera_2",
                "identityGroupId": identity,
                "localPath": path.name,
                "sequenceId": "seq_002",
                "sha256": "abc",
                "subset": "query",
            }
        )
    source = root / "source.jsonl"
    source.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
    summary = build_review_manifest(root, source, tmp_path / "out")
    assert summary["galleryIdentityCount"] == 11

