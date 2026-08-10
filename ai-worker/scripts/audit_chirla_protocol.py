from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

JsonValue = str | int | bool | None | list["JsonValue"] | dict[str, "JsonValue"]


class ManifestAuditError(ValueError):
    pass


def _load_rows(path: Path) -> list[dict[str, JsonValue]]:
    rows: list[dict[str, JsonValue]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row: JsonValue = json.loads(line)
        if not isinstance(row, dict):
            raise ManifestAuditError("each manifest line must be a JSON object")
        rows.append(row)
    return rows


def _text(row: dict[str, JsonValue], key: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value:
        raise ManifestAuditError(f"manifest field {key!r} must be non-empty text")
    return value


def audit_protocol(path: Path) -> dict[str, JsonValue]:
    rows = _load_rows(path)
    gallery_by_identity: dict[str, list[dict[str, JsonValue]]] = defaultdict(list)
    queries: list[dict[str, JsonValue]] = []
    for row in rows:
        role = _text(row, "benchmarkRole")
        identity = _text(row, "identityGroupId")
        if role == "gallery":
            gallery_by_identity[identity].append(row)
        elif role == "query":
            queries.append(row)

    intersection = {
        _text(query, "identityGroupId")
        for query in queries
        if _text(query, "identityGroupId") in gallery_by_identity
    }
    eligible_queries = [
        query for query in queries if _text(query, "identityGroupId") in intersection
    ]

    same_camera_positive = 0
    same_sequence_positive = 0
    strict_cross_camera_sequence_eligible = 0
    camera_overlap_identities: set[str] = set()
    for query in eligible_queries:
        identity = _text(query, "identityGroupId")
        positives = gallery_by_identity[identity]
        query_camera = _text(query, "cameraId")
        query_sequence = _text(query, "sequenceId")
        if any(_text(item, "cameraId") == query_camera for item in positives):
            same_camera_positive += 1
            camera_overlap_identities.add(identity)
        if any(_text(item, "sequenceId") == query_sequence for item in positives):
            same_sequence_positive += 1
        if any(
            _text(item, "cameraId") != query_camera
            and _text(item, "sequenceId") != query_sequence
            for item in positives
        ):
            strict_cross_camera_sequence_eligible += 1

    return {
        "schemaVersion": "chirla-protocol-audit-v1",
        "manifest": str(path),
        "manifestSha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "manifestRows": len(rows),
        "galleryQueryIdentityIntersection": len(intersection),
        "eligibleQueryCount": len(eligible_queries),
        "identitiesWithSameCameraAcrossRoles": len(camera_overlap_identities),
        "queriesWithSameCameraPositive": same_camera_positive,
        "queriesWithSameSequencePositive": same_sequence_positive,
        "strictCrossCameraSequenceEligibleQueries": strict_cross_camera_sequence_eligible,
        "strictCrossCameraSequenceEvaluationAvailable": (
            strict_cross_camera_sequence_eligible > 0
        ),
        "conclusion": (
            "CHIRLA gallery/query retrieval proxy has camera and sequence overlap; "
            "it is not a strict cross-camera generalization benchmark."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_protocol(args.manifest)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()

