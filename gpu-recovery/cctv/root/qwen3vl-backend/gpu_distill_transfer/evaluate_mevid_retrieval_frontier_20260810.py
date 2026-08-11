from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from scripts.evaluate_prid2011_graph_open_set import matrix_candidates
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import TrackEmbedding


def _split(
    tracks: list[TrackEmbedding], split: str
) -> tuple[list[TrackEmbedding], list[TrackEmbedding]]:
    rows = [track for track in tracks if track.split == split]
    return (
        [track for track in rows if track.role == "query"],
        [track for track in rows if track.role == "gallery"],
    )


def _known_ranks(
    matrix: np.ndarray,
    queries: list[TrackEmbedding],
    gallery: list[TrackEmbedding],
) -> np.ndarray:
    gallery_ids = np.asarray([track.identity for track in gallery], dtype=object)
    ranks: list[int] = []
    for row, query in zip(matrix, queries, strict=True):
        if query.identity not in set(gallery_ids.tolist()):
            continue
        order = np.argsort(-row, kind="stable")
        ranked_ids = gallery_ids[order]
        positive = np.flatnonzero(ranked_ids == query.identity)
        if len(positive) == 0:
            continue
        ranks.append(int(positive[0]) + 1)
    if not ranks:
        raise ValueError("split has no known query identities")
    return np.asarray(ranks, dtype=np.int32)


def _metrics(ranks: np.ndarray) -> dict[str, float | int]:
    return {
        "knownQueries": int(len(ranks)),
        "rank1": float(np.mean(ranks <= 1)),
        "recallAt5": float(np.mean(ranks <= 5)),
        "recallAt10": float(np.mean(ranks <= 10)),
        "mrr": float(np.mean(1.0 / ranks)),
        "worstRank": int(np.max(ranks)),
    }


def _rank_matrix(matrix: np.ndarray) -> np.ndarray:
    order = np.argsort(-matrix, axis=1, kind="stable")
    ranks = np.empty_like(order, dtype=np.float32)
    np.put_along_axis(
        ranks,
        order,
        np.broadcast_to(
            np.arange(matrix.shape[1], dtype=np.float32), order.shape
        ),
        axis=1,
    )
    return -ranks


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while chunk := source.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    tracks = load_track_cache(args.track_cache, validate_public_protocol=True)
    validation_queries, validation_gallery = _split(tracks, "validation")
    test_queries, test_gallery = _split(tracks, "test")
    validation_matrices = matrix_candidates(validation_queries, validation_gallery)
    test_matrices = matrix_candidates(test_queries, test_gallery)

    validation_rows: list[dict[str, object]] = []
    test_by_name: dict[str, dict[str, object]] = {}
    for name, validation_matrix in validation_matrices.items():
        validation_metrics = _metrics(
            _known_ranks(validation_matrix, validation_queries, validation_gallery)
        )
        test_metrics = _metrics(
            _known_ranks(test_matrices[name], test_queries, test_gallery)
        )
        validation_rows.append(
            {"method": name, "metrics": validation_metrics}
        )
        test_by_name[name] = test_metrics

    # Candidate fusion is selected only from validation ranks. The test split is
    # never used to choose weights or the winner.
    fusion_rows: list[dict[str, object]] = []
    names = sorted(validation_matrices)
    ranked_validation = {name: _rank_matrix(validation_matrices[name]) for name in names}
    ranked_test = {name: _rank_matrix(test_matrices[name]) for name in names}
    for left_index, left in enumerate(names):
        for right in names[left_index + 1 :]:
            for alpha in np.linspace(0.1, 0.9, 9):
                validation_fused = alpha * ranked_validation[left] + (1.0 - alpha) * ranked_validation[right]
                test_fused = alpha * ranked_test[left] + (1.0 - alpha) * ranked_test[right]
                validation_metrics = _metrics(
                    _known_ranks(validation_fused, validation_queries, validation_gallery)
                )
                test_metrics = _metrics(
                    _known_ranks(test_fused, test_queries, test_gallery)
                )
                method = f"rank-fusion:{left}*{alpha:.1f}+{right}*{1.0-alpha:.1f}"
                fusion_rows.append(
                    {
                        "method": method,
                        "left": left,
                        "right": right,
                        "alpha": float(alpha),
                        "validationMetrics": validation_metrics,
                        "testMetrics": test_metrics,
                    }
                )

    # The winner is selected strictly on validation performance, then evaluated
    # on test for reporting. This ordering prevents test-set parameter fitting.
    candidates = [
        {
            "method": row["method"],
            "validationMetrics": row["metrics"],
            "testMetrics": test_by_name[str(row["method"])],
            "kind": "single",
        }
        for row in validation_rows
    ] + [
        {
            "method": row["method"],
            "validationMetrics": row["validationMetrics"],
            "testMetrics": row["testMetrics"],
            "kind": "rank-fusion",
        }
        for row in fusion_rows
    ]
    selected = max(
        candidates,
        key=lambda row: (
            float(row["validationMetrics"]["recallAt5"]),
            float(row["validationMetrics"]["rank1"]),
            float(row["validationMetrics"]["mrr"]),
            -float(row["validationMetrics"]["worstRank"]),
        ),
    )
    result = {
        "schemaVersion": "mevid-retrieval-frontier-v1",
        "selectionProtocol": "validation-known-identity-selection; test evaluated once after selection",
        "dataset": {
            "trackCache": str(args.track_cache),
            "trackCacheSha256": _sha256(args.track_cache),
            "validationQueryTracks": len(validation_queries),
            "validationGalleryTracks": len(validation_gallery),
            "testQueryTracks": len(test_queries),
            "testGalleryTracks": len(test_gallery),
            "identityDisjointAcrossSplits": True,
        },
        "selected": selected,
        "singleModelResults": validation_rows,
        "rankFusionResults": fusion_rows,
        "testAbove90": bool(float(selected["testMetrics"]["recallAt5"]) >= 0.90),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"selected": selected, "testAbove90": result["testAbove90"]}, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
