from pathlib import Path

import pytest

from scripts.build_project_track_heldout_manifest import (
    build_track_heldout_records,
)


def _rows(tmp_path: Path, tracks: int = 10, frames: int = 8) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for track_index in range(tracks):
        track_id = f"video-track-{track_index:04d}"
        for frame_index in range(frames):
            relative = Path("crops") / track_id / f"{frame_index:06d}.jpg"
            image_path = tmp_path / relative
            image_path.parent.mkdir(parents=True, exist_ok=True)
            image_path.write_bytes(f"{track_id}-{frame_index}".encode())
            rows.append(
                {
                    "trackId": track_id,
                    "framePath": relative.as_posix(),
                    "timestampMs": frame_index * 100,
                    "sequenceId": "video",
                    "cameraId": "camera",
                }
            )
    return rows


def test_builds_temporally_disjoint_gallery_and_query(tmp_path: Path) -> None:
    rows = _rows(tmp_path)
    tracks = [f"video-track-{index:04d}" for index in range(10)]

    records = build_track_heldout_records(rows, tmp_path, tracks)

    assert len(records) == 80
    assert {record["benchmarkRole"] for record in records} == {"gallery", "query"}
    assert len({record["identityGroupId"] for record in records}) == 10
    for track_id in tracks:
        track_records = [
            record for record in records if record["identityGroupId"] == track_id
        ]
        gallery_times = [
            record["timestampMs"]
            for record in track_records
            if record["benchmarkRole"] == "gallery"
        ]
        query_times = [
            record["timestampMs"]
            for record in track_records
            if record["benchmarkRole"] == "query"
        ]
        assert max(gallery_times) < min(query_times)


def test_rejects_fewer_than_ten_reviewed_tracks(tmp_path: Path) -> None:
    rows = _rows(tmp_path, tracks=9)
    tracks = [f"video-track-{index:04d}" for index in range(9)]

    with pytest.raises(ValueError, match="at least 10"):
        build_track_heldout_records(rows, tmp_path, tracks)

