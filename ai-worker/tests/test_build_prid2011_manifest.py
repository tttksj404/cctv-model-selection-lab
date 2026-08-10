from __future__ import annotations

from pathlib import Path

import pytest

from scripts.build_prid2011_manifest import SplitConfig, build_records


def _make_camera(root: Path, camera: str, identities: range) -> None:
    for identity in identities:
        identity_dir = root / camera / f"person_{identity:04d}"
        identity_dir.mkdir(parents=True, exist_ok=True)
        for frame in range(3):
            (identity_dir / f"frame_{frame:04d}.png").write_bytes(
                f"{camera}-{identity}-{frame}".encode()
            )


def test_builds_identity_disjoint_cross_camera_track_split(tmp_path: Path) -> None:
    _make_camera(tmp_path, "cam_a", range(1, 15))
    _make_camera(tmp_path, "cam_b", range(1, 17))

    records = build_records(
        tmp_path,
        SplitConfig(
            train_identities=4,
            validation_identities=3,
            shared_identities=14,
        ),
    )

    shared_records = [
        row for row in records if row["identityKind"] == "shared-target"
    ]
    identities_by_split = {
        split: {
            str(row["identityGroupId"])
            for row in shared_records
            if row["split"] == split
        }
        for split in ("train", "validation", "test")
    }
    assert identities_by_split["train"] == {
        "prid-shared-001",
        "prid-shared-002",
        "prid-shared-003",
        "prid-shared-004",
    }
    assert identities_by_split["validation"] == {
        "prid-shared-005",
        "prid-shared-006",
        "prid-shared-007",
    }
    assert identities_by_split["test"] == {
        f"prid-shared-{identity:03d}" for identity in range(8, 15)
    }
    assert not (
        identities_by_split["train"] & identities_by_split["validation"]
        or identities_by_split["train"] & identities_by_split["test"]
        or identities_by_split["validation"] & identities_by_split["test"]
    )

    evaluation_records = [
        row for row in shared_records if row["split"] != "train"
    ]
    assert {
        (row["cameraId"], row["benchmarkRole"])
        for row in evaluation_records
    } == {("cam_a", "query"), ("cam_b", "gallery")}
    assert all(
        row["trackId"]
        == f"{row['split']}:{row['cameraId']}:{row['identityGroupId']}"
        for row in records
    )
    assert all(len(str(row["sha256"])) == 64 for row in records)


def test_namespaces_single_camera_distractors(tmp_path: Path) -> None:
    _make_camera(tmp_path, "cam_a", range(1, 13))
    _make_camera(tmp_path, "cam_b", range(1, 11))

    records = build_records(
        tmp_path,
        SplitConfig(
            train_identities=4,
            validation_identities=2,
            shared_identities=10,
        ),
    )

    distractors = [row for row in records if row["identityKind"] == "distractor"]
    assert {
        str(row["identityGroupId"]) for row in distractors
    } == {"prid-cam-a-only-011", "prid-cam-a-only-012"}
    assert {row["benchmarkRole"] for row in distractors} == {"query"}
    assert {row["split"] for row in distractors} == {"validation", "test"}


def test_rejects_too_few_shared_identities(tmp_path: Path) -> None:
    _make_camera(tmp_path, "cam_a", range(1, 6))
    _make_camera(tmp_path, "cam_b", range(1, 6))

    with pytest.raises(ValueError, match="shared identities"):
        build_records(
            tmp_path,
            SplitConfig(
                train_identities=4,
                validation_identities=2,
                shared_identities=5,
            ),
        )

