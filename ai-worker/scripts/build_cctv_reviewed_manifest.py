from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

VIDEO_REVIEW = {
    "IMG_3565": {
        "split": "test_landscape",
        "condition": "landscape_room",
        "identity": "person-local-01",
        "color": ["black"],
        "clothing": ["hoodie"],
        "texture": ["solid"],
        "occlusion": "0.10",
        "review_note": "가로 실내 영상의 검정 후드 상의 track",
    },
    "IMG_3567": {
        "split": "test_landscape",
        "condition": "landscape_room",
        "identity": "person-local-01",
        "color": ["navy"],
        "clothing": ["short_sleeve_shirt"],
        "texture": ["solid"],
        "occlusion": "0.10",
        "review_note": "가로 실내 영상의 남색 반팔 상의 track",
    },
    "IMG_3568": {
        "split": "test_portrait_fisheye",
        "condition": "portrait_fisheye",
        "identity": "person-local-01",
        "color": ["navy", "black"],
        "clothing": ["short_sleeve_shirt", "black_outer_layer"],
        "texture": ["solid"],
        "occlusion": "0.25",
        "review_note": "세로 어안 영상의 남색 상의와 검정 외투가 보이는 track",
    },
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _relative_path(workspace: Path, raw: str) -> str:
    path = (workspace / raw).resolve()
    return path.relative_to(workspace.resolve()).as_posix()


def _review_row(row: dict[str, Any], workspace: Path, evidence: Path) -> dict[str, Any]:
    video_id = str(row["sourceVideoId"])
    review = VIDEO_REVIEW.get(video_id)
    if review is None:
        raise ValueError(f"no review mapping for sourceVideoId={video_id}")
    source_frame = (workspace / str(row["sourceFramePath"])).resolve()
    crop = (workspace / str(row["cropPath"])).resolve()
    if not source_frame.is_file() or not crop.is_file():
        raise FileNotFoundError(f"missing source or crop for {row['sampleId']}")
    quality = float(row.get("sourceQuality") or 0.0)
    return {
        "schemaVersion": "cctv-attribute-sample-v1",
        "sampleId": row["sampleId"],
        "caseId": row["caseId"],
        "sourceFramePath": _relative_path(workspace, str(row["sourceFramePath"])),
        "sourceFrameSha256": _sha256(source_frame),
        "sourceVideoId": video_id,
        "cameraId": row["cameraId"],
        "sequenceId": row["sequenceId"],
        "sourceTrackId": row["sourceTrackId"],
        "conditionGroupId": review["condition"],
        "sourceSplit": "test",
        "split": review["split"],
        "cropPath": _relative_path(workspace, str(row["cropPath"])),
        "cropSha256": _sha256(crop),
        "augmentation": "original",
        "timestampMs": row["timestampMs"],
        "identityGroupId": review["identity"],
        "targetRole": "target",
        "labelStatus": "human_reviewed",
        "labels": {
            "color": review["color"],
            "clothing": review["clothing"],
            "texture": review["texture"],
            "quality": [f"{quality:.6f}"],
            "occlusion": [review["occlusion"]],
        },
        "sourceQuality": quality,
        "sourceQualityFlags": ["detector_candidate", "local_visual_review"],
        "sourceAttributes": {
            "color": review["color"],
            "clothing": review["clothing"],
            "texture": review["texture"],
            "carriedItem": [],
            "visibility": "visible_with_condition_variation",
        },
        "attributeEvidenceFrameIds": [row["sampleId"]],
        "trainingEligible": True,
        "approvalStatus": "approved",
        "identityReviewStatus": "human_reviewed",
        "teacherAgreement": False,
        "teacherSourceKind": "none",
        "teacherModel": None,
        "teacherTermsStatus": "not_applicable",
        "labelProvenance": "human_review",
        "reviewEvidencePath": evidence.relative_to(workspace).as_posix(),
        "reviewEvidenceSha256": _sha256(evidence),
        "teacherEvidencePath": None,
        "teacherEvidenceSha256": None,
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a reviewed, original-frame CCTV manifest from the local pilot draft."
    )
    parser.add_argument("--input-manifest", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    return parser


def main() -> int:
    args = _parser().parse_args()
    workspace = args.workspace.resolve()
    evidence = args.evidence.resolve()
    if not evidence.is_file():
        raise FileNotFoundError(f"review evidence does not exist: {evidence}")
    rows: list[dict[str, Any]] = []
    for line in args.input_manifest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("augmentation") == "original":
            rows.append(_review_row(row, workspace, evidence))
    if not rows:
        raise ValueError("input manifest contains no original rows")
    output = args.output_manifest.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(output)
    summary = {
        "schemaVersion": "cctv-reviewed-manifest-summary-v1",
        "status": "valid_for_local_pilot_evaluation",
        "rows": len(rows),
        "sourceVideos": sorted({row["sourceVideoId"] for row in rows}),
        "identityGroups": sorted({row["identityGroupId"] for row in rows}),
        "sourceTracks": sorted({row["sourceTrackId"] for row in rows}),
        "splitCounts": {
            split: sum(row["split"] == split for row in rows)
            for split in sorted({row["split"] for row in rows})
        },
        "identityReviewBasis": "single_local_visual_review_with_existing_identity_pilot_record",
        "notGeneral85Evidence": True,
    }
    output.with_suffix(".summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
