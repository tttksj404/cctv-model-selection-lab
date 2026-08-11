"""Evaluate the CCTV retrieval unit used by the worker: one persistent track.

The frame-level score matrix is intentionally not treated as 95 independent
decisions.  A CCTV worker emits one candidate per tracker track, so all frames
belonging to one track are averaged before ranking identities.  The evaluator
keeps the frame-level result beside the track-level result to make metric-unit
changes auditable.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import numpy as np


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"metadata root must be an object: {path}")
    return cast(dict[str, Any], value)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rank(scores: np.ndarray, targets: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, axis=1, kind="stable")
    return np.where(order == targets[:, None])[1] + 1


def _metrics(ranks: np.ndarray) -> dict[str, int | float]:
    return {
        "count": len(ranks),
        "rank1Hits": int(np.sum(ranks <= 1)),
        "recallAt5Hits": int(np.sum(ranks <= 5)),
        "rank1": float(np.mean(ranks <= 1)),
        "recallAt5": float(np.mean(ranks <= 5)),
        "mrr": float(np.mean(1.0 / ranks)),
        "worstRank": int(np.max(ranks)),
    }


def _require_list(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key)
    if not isinstance(value, list):
        raise ValueError(f"metadata.{key} must be a string list")
    items = cast(list[Any], value)
    if not all(isinstance(item, str) for item in items):
        raise ValueError(f"metadata.{key} must be a string list")
    return cast(list[str], items)


def _track_rows(
    metadata: dict[str, Any],
    scores: np.ndarray,
    identities: list[str],
) -> tuple[np.ndarray, np.ndarray, list[dict[str, Any]]]:
    query_paths = _require_list(metadata, "query_path")
    query_identity = _require_list(metadata, "query_identity")
    query_camera = _require_list(metadata, "query_camera")
    query_sequence = _require_list(metadata, "query_sequence")
    lengths = {
        len(query_paths),
        len(query_identity),
        len(query_camera),
        len(query_sequence),
        scores.shape[0],
    }
    if len(lengths) != 1:
        raise ValueError(f"query metadata and scores have inconsistent lengths: {lengths}")

    grouped: dict[str, list[int]] = defaultdict(list)
    for index, path in enumerate(query_paths):
        grouped[Path(path).parent.as_posix()].append(index)
    track_scores: list[np.ndarray] = []
    targets: list[int] = []
    receipts: list[dict[str, Any]] = []
    for track_id, indices in grouped.items():
        identities_in_track = {query_identity[index] for index in indices}
        cameras_in_track = {query_camera[index] for index in indices}
        sequences_in_track = {query_sequence[index] for index in indices}
        if (
            len(identities_in_track) != 1
            or len(cameras_in_track) != 1
            or len(sequences_in_track) != 1
        ):
            raise ValueError(f"track provenance is inconsistent: {track_id}")
        identity = next(iter(identities_in_track))
        if identity not in identities:
            raise ValueError(f"track identity is absent from gallery identities: {identity}")
        track_scores.append(scores[indices].mean(axis=0))
        targets.append(identities.index(identity))
        receipts.append(
            {
                "trackId": track_id,
                "frameCount": len(indices),
                "identity": identity,
                "camera": next(iter(cameras_in_track)),
                "sequence": next(iter(sequences_in_track)),
            }
        )
    if not track_scores:
        raise ValueError("no query tracks were found")
    return np.stack(track_scores), np.asarray(targets, dtype=np.int64), receipts


def evaluate(
    scores_path: Path,
    metadata_path: Path,
    *,
    model_array: str,
    target: float,
    manifest_sha256: str,
    checkpoint_sha256: str,
) -> dict[str, Any]:
    metadata = _read_json(metadata_path)
    if metadata.get("protocol") != "strict-cross-camera-sequence":
        raise ValueError("track gate requires strict-cross-camera-sequence metadata")
    identities = _require_list(metadata, "identities")
    loaded = np.load(scores_path)
    if model_array not in loaded.files:
        raise ValueError(f"model score array is missing: {model_array}")
    scores = np.asarray(loaded[model_array], dtype=np.float32)
    query_identity = _require_list(metadata, "query_identity")
    frame_targets = np.asarray(
        [identities.index(identity) for identity in query_identity],
        dtype=np.int64,
    )
    frame_ranks = _rank(scores, frame_targets)
    track_scores, track_targets, tracks = _track_rows(metadata, scores, identities)
    track_ranks = _rank(track_scores, track_targets)
    by_sequence: dict[str, dict[str, int | float]] = {}
    for sequence in sorted({str(track["sequence"]) for track in tracks}):
        indices = np.asarray(
            [index for index, track in enumerate(tracks) if track["sequence"] == sequence],
            dtype=np.int64,
        )
        by_sequence[sequence] = _metrics(track_ranks[indices])

    result: dict[str, Any] = {
        "schemaVersion": "eyesonu-chirla-track-evidence-v1",
        "dataset": "CHIRLA complete local manifest",
        "datasetStatus": "public-proxy-not-project-CCTV",
        "protocol": "strict-cross-camera-sequence",
        "metricUnit": "persistent-query-track",
        "model": "SOLIDER official Swin-B MSMT17 checkpoint",
        "modelArray": model_array,
        "aggregation": "mean identity score over frames in one query track",
        "counts": {
            "frameQueries": len(frame_ranks),
            "queryTracks": len(track_ranks),
            "galleryIdentities": len(identities),
        },
        "frameLevel": _metrics(frame_ranks),
        "trackLevel": _metrics(track_ranks),
        "bySequence": by_sequence,
        "promotion": {
            "targetRecallAt5": target,
            "observedRecallAt5": float(np.mean(track_ranks <= 5)),
            "passed": bool(np.mean(track_ranks <= 5) >= target),
            "interpretation": (
                "track-level candidate retrieval gate passed on a public proxy; "
                "this is not a project-CCTV deployment guarantee"
            ),
        },
        "provenance": {
            "scoreMatrixSha256": _sha256(scores_path),
            "metadataSha256": _sha256(metadata_path),
            "manifestSha256": manifest_sha256,
            "checkpointSha256": checkpoint_sha256,
        },
        "trackReceipts": tracks,
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--model-array", default="solider_reid_swin_base_msmt17")
    parser.add_argument("--target", type=float, default=0.85)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(
        args.scores,
        args.metadata,
        model_array=args.model_array,
        target=args.target,
        manifest_sha256=args.manifest_sha256,
        checkpoint_sha256=args.checkpoint_sha256,
    )
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    promotion = result["promotion"]
    print(
        f"{'PASS' if promotion['passed'] else 'FAIL'} | "
        f"track Recall@5={promotion['observedRecallAt5']:.4f}; "
        f"tracks={result['counts']['queryTracks']}; "
        f"frames={result['counts']['frameQueries']}"
    )
    return 0 if promotion["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
