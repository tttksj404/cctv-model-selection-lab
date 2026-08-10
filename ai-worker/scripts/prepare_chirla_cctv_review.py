from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

TARGET_IDENTITIES = ("1", "2", "3", "4", "5", "6", "7", "9", "10", "12", "14")
DISTRACTOR_IDENTITIES = ("-1", "-2", "-3", "-4", "-5", "-6", "-7", "-8", "-9", "-10", "-11")


class SourceRow(TypedDict, total=False):
    benchmarkRole: str
    cameraId: str
    identityGroupId: str
    localPath: str
    sequenceId: str
    sha256: str
    subset: str


class ReviewRow(TypedDict):
    caseId: str
    videoId: str
    cameraId: str
    conditionGroupId: str
    trackId: str
    split: str
    targetRole: str
    identityGroupId: str
    frameCount: int
    framePath: str
    sourceIdentity: str
    sourceRole: str
    sequenceId: str
    subset: str
    frameSha256: str


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(path: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        payload = json.loads(line)
        if not isinstance(payload, dict):
            raise ValueError(f"source row {line_number} is not an object")
        rows.append(payload)
    return rows


def _group_key(row: SourceRow) -> tuple[str, str, str, str]:
    return (
        row["identityGroupId"],
        row["sequenceId"],
        row["cameraId"],
        row.get("subset", "unknown"),
    )


def _select_groups(
    rows: list[SourceRow], role: str, identities: tuple[str, ...]
) -> list[list[SourceRow]]:
    grouped: dict[tuple[str, str, str, str], list[SourceRow]] = defaultdict(list)
    wanted = set(identities)
    for row in rows:
        if row.get("benchmarkRole") == role and row.get("identityGroupId") in wanted:
            grouped[_group_key(row)].append(row)
    result: list[list[SourceRow]] = []
    for identity in identities:
        candidates = sorted(
            (group for key, group in grouped.items() if key[0] == identity),
            key=lambda group: (group[0].get("sequenceId", ""), group[0].get("cameraId", "")),
        )
        if not candidates:
            raise ValueError(f"no {role} track for identity {identity}")
        result.append(candidates[0])
    return result


def _track_rows(
    groups: list[list[SourceRow]],
    *,
    role: str,
    identities: tuple[str, ...],
    root: Path,
    target_queries: bool = False,
) -> list[ReviewRow]:
    output: list[ReviewRow] = []
    for group, source_identity in zip(groups, identities, strict=True):
        first = group[0]
        canonical_identity = (
            f"chirla-id-{source_identity.lstrip('-')}"
            if role == "gallery" or target_queries
            else f"chirla-distractor-{source_identity.lstrip('-')}"
        )
        camera = first["cameraId"].split("_")[1]
        source_key = source_identity.replace("-", "neg-")
        track_id = f"chirla-{role}-{source_key}-{first['sequenceId']}-{camera}"
        for row in group:
            path = (root / row["localPath"]).resolve()
            if root not in path.parents or not path.is_file():
                raise ValueError(f"source frame is outside dataset or missing: {row['localPath']}")
            output.append(
                {
                    "caseId": "cctv-external-chirla-20260727",
                    "videoId": f"chirla-{first.get('subset', 'unknown')}-{first['sequenceId']}",
                    "cameraId": first["cameraId"],
                    "conditionGroupId": "chirla-multi-camera-long-term",
                    "trackId": track_id,
                    "split": "gallery" if role == "gallery" else "test_landscape",
                    "targetRole": "target" if role == "gallery" or target_queries else "distractor",
                    "identityGroupId": canonical_identity,
                    "frameCount": len(group),
                    "framePath": row["localPath"],
                    "sourceIdentity": source_identity,
                    "sourceRole": row.get("benchmarkRole", role),
                    "sequenceId": row["sequenceId"],
                    "subset": row.get("subset", "unknown"),
                    "frameSha256": row["sha256"],
                }
            )
    return output


def build_review_manifest(
    root: Path, source_manifest: Path, output_dir: Path
) -> dict[str, int | str | list[str]]:
    root = root.resolve()
    rows = _read_rows(source_manifest)
    gallery_groups = _select_groups(rows, "gallery", TARGET_IDENTITIES)
    target_query_groups = _select_groups(rows, "query", TARGET_IDENTITIES)
    distractor_query_groups = _select_groups(rows, "query", DISTRACTOR_IDENTITIES)
    selected = _track_rows(gallery_groups, role="gallery", identities=TARGET_IDENTITIES, root=root)
    selected += _track_rows(
        target_query_groups,
        role="query",
        identities=TARGET_IDENTITIES,
        root=root,
        target_queries=True,
    )
    selected += _track_rows(
        distractor_query_groups, role="query", identities=DISTRACTOR_IDENTITIES, root=root
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "manifest.jsonl"
    manifest_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected),
        encoding="utf-8",
    )
    adjudication = [
        {
            "trackId": row["trackId"],
            "identityGroupId": row["identityGroupId"],
            "sourceLabel": row["sourceIdentity"],
            "sourceLabelReviewer": "CHIRLA official benchmark directory label",
            "independentReviewer": "project_visual_adjudicator_pending",
            "adjudicationStatus": "pending_visual_and_attribute_review",
            "representativeFramePath": row["framePath"],
        }
        for row in selected
        if not row["trackId"].startswith("chirla-gallery")
    ]
    (output_dir / "adjudication.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in adjudication),
        encoding="utf-8",
    )
    summary: dict[str, int | str | list[str]] = {
        "schemaVersion": "cctv-external-chirla-review-v1",
        "dataset": "CHIRLA",
        "sourceManifestSha256": _sha256(source_manifest),
        "manifestSha256": _sha256(manifest_path),
        "galleryIdentityCount": len(TARGET_IDENTITIES),
        "targetQueryTrackCount": len(TARGET_IDENTITIES),
        "distractorQueryTrackCount": len(DISTRACTOR_IDENTITIES),
        "totalTrackCount": len(TARGET_IDENTITIES) * 2 + len(DISTRACTOR_IDENTITIES),
        "frameRowCount": len(selected),
        "targetIdentities": list(TARGET_IDENTITIES),
        "distractorIdentities": list(DISTRACTOR_IDENTITIES),
        "adjudicationStatus": "pending_visual_and_attribute_review",
        "sourceLicense": "CC BY 4.0; see source manifest and CHIRLA README",
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build a sealed CHIRLA CCTV identity review subset"
    )
    parser.add_argument("--root", type=Path, default=Path("experiments/data/chirla"))
    parser.add_argument("--source-manifest", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    source_manifest = args.source_manifest or args.root / "chirla_identity_manifest.jsonl"
    summary = build_review_manifest(args.root, source_manifest, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

