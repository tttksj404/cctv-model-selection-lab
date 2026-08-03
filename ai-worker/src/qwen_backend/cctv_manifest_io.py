from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping
from pathlib import Path

from .cctv_identity_evaluation import CCTVDataError, TrackReference, TrackRetrievalPrediction

_REFERENCE_FIELDS = (
    "caseId",
    "videoId",
    "cameraId",
    "conditionGroupId",
    "trackId",
    "split",
    "targetRole",
    "identityGroupId",
)


def _read_jsonl(path: Path) -> Iterable[Mapping[str, object]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CCTVDataError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(payload, dict):
            raise CCTVDataError(f"JSONL row is not an object at {path}:{line_number}")
        yield payload


def load_track_references(path: Path) -> tuple[TrackReference, ...]:
    references: dict[str, TrackReference] = {}
    frame_counts: dict[str, int] = {}
    try:
        rows = _read_jsonl(path)
        for row in rows:
            reference_payload = {field: row.get(field) for field in _REFERENCE_FIELDS}
            try:
                reference = TrackReference.model_validate(reference_payload)
            except ValueError as exc:
                raise CCTVDataError(f"invalid track reference in {path}: {exc}") from exc
            existing = references.get(reference.track_id)
            if existing is not None and _identity_fields(existing) != _identity_fields(reference):
                raise CCTVDataError(f"track metadata changes within trackId: {reference.track_id}")
            references.setdefault(reference.track_id, reference)
            frame_counts[reference.track_id] = frame_counts.get(reference.track_id, 0) + 1
    except OSError as exc:
        raise CCTVDataError(f"cannot read JSONL file: {path}") from exc

    return tuple(
        references[track_id].model_copy(update={"frame_count": frame_counts[track_id]})
        for track_id in sorted(references)
    )


def load_track_predictions(path: Path) -> tuple[TrackRetrievalPrediction, ...]:
    predictions: list[TrackRetrievalPrediction] = []
    try:
        rows = _read_jsonl(path)
        for row in rows:
            try:
                predictions.append(TrackRetrievalPrediction.model_validate(row))
            except ValueError as exc:
                raise CCTVDataError(f"invalid track prediction in {path}: {exc}") from exc
    except OSError as exc:
        raise CCTVDataError(f"cannot read JSONL file: {path}") from exc
    return tuple(predictions)


def manifest_sha256(path: Path) -> str:
    return _sha256(path.read_bytes())


def identity_label_sha256(references: tuple[TrackReference, ...]) -> str:
    canonical = "\n".join(
        "|".join(
            (
                reference.track_id,
                reference.split,
                reference.target_role,
                reference.identity_group_id or "",
            )
        )
        for reference in references
    )
    return _sha256(canonical.encode("utf-8"))


def _identity_fields(reference: TrackReference) -> tuple[str, ...]:
    return (
        reference.case_id,
        reference.video_id,
        reference.camera_id,
        reference.condition_group_id,
        reference.split,
        reference.target_role,
        reference.identity_group_id or "",
    )


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
