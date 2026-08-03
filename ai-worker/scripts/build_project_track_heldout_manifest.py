from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Iterable, Sequence
from pathlib import Path

DEFAULT_REVIEWED_TRACKS = (
    "IMG_3617-track-0002",
    "IMG_3617-track-0003",
    "IMG_3617-track-0004",
    "IMG_3617-track-0005",
    "IMG_3617-track-0007",
    "IMG_3617-track-0008",
    "IMG_3617-track-0009",
    "IMG_3617-track-0010",
    "IMG_3617-track-0017",
    "IMG_3617-track-0074",
)


def _load_rows(path: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _required_text(row: dict[str, object], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be non-empty text")
    return value


def _required_timestamp(row: dict[str, object]) -> int:
    value = row.get("timestampMs")
    if not isinstance(value, int):
        raise ValueError("timestampMs must be an integer")
    return value


def build_track_heldout_records(
    rows: Iterable[dict[str, object]],
    source_root: Path,
    selected_tracks: Sequence[str],
    gallery_count: int = 4,
    query_count: int = 4,
) -> list[dict[str, object]]:
    if len(set(selected_tracks)) < 10:
        raise ValueError("project track-heldout gate requires at least 10 reviewed tracks")
    if gallery_count < 1 or query_count < 1:
        raise ValueError("gallery_count and query_count must be positive")

    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        track_id = _required_text(row, "trackId")
        if track_id in selected_tracks:
            grouped[track_id].append(row)

    records: list[dict[str, object]] = []
    required_count = gallery_count + query_count
    for track_id in selected_tracks:
        track_rows = sorted(
            grouped.get(track_id, []),
            key=lambda row: (_required_timestamp(row), _required_text(row, "framePath")),
        )
        if len(track_rows) < required_count:
            raise ValueError(
                f"{track_id} requires at least {required_count} crops, found {len(track_rows)}"
            )
        selected = [
            *[(row, "gallery") for row in track_rows[:gallery_count]],
            *[(row, "query") for row in track_rows[-query_count:]],
        ]
        gallery_end = _required_timestamp(selected[gallery_count - 1][0])
        query_start = _required_timestamp(selected[gallery_count][0])
        if gallery_end >= query_start:
            raise ValueError(f"{track_id} has no temporal gap between gallery and query")

        for row, role in selected:
            relative_path = Path(_required_text(row, "framePath"))
            image_path = source_root / relative_path
            if not image_path.is_file():
                raise FileNotFoundError(image_path)
            records.append(
                {
                    "schemaVersion": "project-cctv-track-heldout-v1",
                    "dataset": "EyesOnU project CCTV",
                    "task": "person-reidentification",
                    "evaluationScope": "same-camera-temporal-track-proxy",
                    "benchmarkRole": role,
                    "split": "project_track_heldout",
                    "sequenceId": _required_text(row, "sequenceId"),
                    "cameraId": _required_text(row, "cameraId"),
                    "identityGroupId": track_id,
                    "trackId": track_id,
                    "timestampMs": _required_timestamp(row),
                    "localPath": relative_path.as_posix(),
                    "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
                    "labelSource": "manual visual stable-track review on 2026-07-28",
                    "identityIsProjectReviewed": True,
                    "domainStatus": "project-CCTV-track-local-identity-proxy",
                }
            )
    return records


def _write_jsonl(path: Path, rows: Sequence[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a reviewed project CCTV temporal track-heldout manifest"
    )
    parser.add_argument(
        "--source-manifest",
        type=Path,
        default=Path(
            "experiments/data/cctv_real/multitrack_20260728/manifest.jsonl"
        ),
    )
    parser.add_argument("--source-root", type=Path, default=Path("."))
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "experiments/data/cctv_real/multitrack_20260728/"
            "project_track_heldout_manifest.jsonl"
        ),
    )
    parser.add_argument("--gallery-count", type=int, default=4)
    parser.add_argument("--query-count", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    records = build_track_heldout_records(
        _load_rows(args.source_manifest),
        args.source_root,
        DEFAULT_REVIEWED_TRACKS,
        gallery_count=args.gallery_count,
        query_count=args.query_count,
    )
    _write_jsonl(args.output, records)
    summary = {
        "schemaVersion": "project-cctv-track-heldout-v1",
        "records": len(records),
        "reviewedIdentityTracks": len(DEFAULT_REVIEWED_TRACKS),
        "galleryRecords": sum(row["benchmarkRole"] == "gallery" for row in records),
        "queryRecords": sum(row["benchmarkRole"] == "query" for row in records),
        "evaluationScope": "same-camera-temporal-track-proxy",
        "strictCrossCameraGeneralizationEvidence": False,
        "strictProxyBenchmark": "CHIRLA identity-heldout",
    }
    summary_path = args.output.with_suffix(".summary.json")
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
