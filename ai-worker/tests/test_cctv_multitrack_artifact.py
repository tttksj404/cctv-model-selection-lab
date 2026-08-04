from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ARTIFACT_ROOT = ROOT / "experiments" / "data" / "cctv_real" / "multitrack_20260728"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@pytest.mark.external_research_artifact
def test_project_track_heldout_artifact_is_complete_and_hash_valid() -> None:
    manifest_path = ARTIFACT_ROOT / "project_track_heldout_manifest.jsonl"
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(rows) == 80
    assert {row["split"] for row in rows} == {"project_track_heldout"}
    assert {row["benchmarkRole"] for row in rows} == {"gallery", "query"}
    assert len({row["identityGroupId"] for row in rows}) == 10
    assert sum(row["benchmarkRole"] == "gallery" for row in rows) == 40
    assert sum(row["benchmarkRole"] == "query" for row in rows) == 40

    for row in rows:
        crop_path = ROOT / row["localPath"]
        assert crop_path.is_file()
        assert _sha256(crop_path) == row["sha256"]


def test_deprecated_package_snapshot_is_not_executable() -> None:
    init_path = ROOT / "package-staging" / "src" / "qwen_backend" / "__init__.py"
    namespace: dict[str, str] = {}

    if not init_path.exists():
        return

    try:
        exec(init_path.read_text(encoding="utf-8"), namespace)
    except RuntimeError as exc:
        assert "deprecated, non-executable snapshot" in str(exc)
    else:
        raise AssertionError("package-staging unexpectedly remained executable")
