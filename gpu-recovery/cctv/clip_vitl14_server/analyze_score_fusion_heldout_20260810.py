from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from pathlib import Path

import numpy as np


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--scores", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def _rank(scores: np.ndarray, target_indices: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, axis=1, kind="stable")
    positions = np.where(order == target_indices[:, None])[1]
    return positions + 1


def _metrics(scores: np.ndarray, target_indices: np.ndarray) -> dict[str, float | int]:
    ranks = _rank(scores, target_indices)
    return {
        "count": len(ranks),
        "rank1_hits": int(np.sum(ranks <= 1)),
        "recall_at_5_hits": int(np.sum(ranks <= 5)),
        "rank1": float(np.mean(ranks <= 1)),
        "recall_at_5": float(np.mean(ranks <= 5)),
        "mrr": float(np.mean(1.0 / ranks)),
        "worst_rank": int(np.max(ranks)),
    }


def _zscore(scores: np.ndarray) -> np.ndarray:
    mean = scores.mean(axis=1, keepdims=True)
    std = scores.std(axis=1, keepdims=True)
    return (scores - mean) / np.maximum(std, 1e-6)


def _minmax(scores: np.ndarray) -> np.ndarray:
    minimum = scores.min(axis=1, keepdims=True)
    maximum = scores.max(axis=1, keepdims=True)
    return (scores - minimum) / np.maximum(maximum - minimum, 1e-6)


def _rank_score(scores: np.ndarray) -> np.ndarray:
    order = np.argsort(-scores, axis=1, kind="stable")
    ranks = np.empty_like(order, dtype=np.float32)
    rank_values = np.broadcast_to(
        np.arange(scores.shape[1], dtype=np.float32), order.shape
    )
    np.put_along_axis(ranks, order, rank_values, axis=1)
    return -ranks


def _weights_2d() -> Iterable[tuple[float, float, float]]:
    for left_index in range(21):
        left = left_index / 20.0
        for middle_index in range(21 - left_index):
            middle = middle_index / 20.0
            right = 1.0 - left - middle
            yield left, middle, right


def _fuse(
    arrays: dict[str, np.ndarray],
    names: tuple[str, str, str],
    weights: tuple[float, float, float],
    rows: np.ndarray,
) -> np.ndarray:
    fused = np.zeros_like(arrays[names[0]][rows], dtype=np.float32)
    for weight, name in zip(weights, names, strict=True):
        fused += weight * arrays[name][rows]
    return fused


def _evaluate_grid(
    arrays: dict[str, np.ndarray],
    target_indices: np.ndarray,
    names: tuple[str, str, str],
    rows: np.ndarray,
) -> dict[str, object]:
    best: dict[str, object] | None = None
    for weights in _weights_2d():
        fused = _fuse(arrays, names, weights, rows)
        metrics = _metrics(fused, target_indices[rows])
        candidate: dict[str, object] = {
            "weights": dict(zip(names, weights, strict=True)),
            "metrics": metrics,
        }
        if best is None or tuple(
            metrics[key] for key in ("recall_at_5", "rank1", "mrr")
        ) > tuple(
            best["metrics"][key]  # type: ignore[index]
            for key in ("recall_at_5", "rank1", "mrr")
        ):
            best = candidate
    if best is None:
        raise ValueError("empty fusion grid")
    return best


def main() -> None:
    args = _args()
    metadata = json.loads(args.metadata.read_text(encoding="utf-8"))
    identities = [str(value) for value in metadata["identities"]]
    query_identities = [str(value) for value in metadata["query_identity"]]
    target_indices = np.asarray(
        [identities.index(value) for value in query_identities],
        dtype=np.int64,
    )
    loaded = np.load(args.scores)
    arrays = {name: np.asarray(loaded[name], dtype=np.float32) for name in loaded.files}
    aliases = {
        "solider_reid_swin_base_msmt17": "solider",
        "siglip2_base": "siglip2",
        "dinov2_base": "dinov2",
        "clip_vit_l14": "clip_l14",
    }
    arrays = {aliases[name]: value for name, value in arrays.items()}
    normalized = {
        "raw": arrays,
        "zscore": {name: _zscore(value) for name, value in arrays.items()},
        "minmax": {name: _minmax(value) for name, value in arrays.items()},
        "rank": {name: _rank_score(value) for name, value in arrays.items()},
    }
    sequence = np.asarray([str(value) for value in metadata["query_sequence"]])
    combinations: dict[str, object] = {}
    for normalization, values in normalized.items():
        combinations[normalization] = {
            "single": {
                name: _metrics(value, target_indices) for name, value in values.items()
            },
            "best_3_model": _evaluate_grid(
                values,
                target_indices,
                ("solider", "siglip2", "dinov2"),
                np.arange(len(target_indices), dtype=np.int64),
            ),
            "best_solider_siglip_clip": _evaluate_grid(
                values,
                target_indices,
                ("solider", "siglip2", "clip_l14"),
                np.arange(len(target_indices), dtype=np.int64),
            ),
        }
    all_rows = np.arange(len(target_indices), dtype=np.int64)
    cv: dict[str, object] = {}
    for normalization, values in normalized.items():
        fold_rows: list[dict[str, object]] = []
        for held_out in sorted(set(sequence)):
            train = all_rows[sequence != held_out]
            test = all_rows[sequence == held_out]
            selected = _evaluate_grid(
                values,
                target_indices,
                ("solider", "siglip2", "dinov2"),
                train,
            )
            weights_object = selected["weights"]
            if not isinstance(weights_object, dict):
                raise TypeError("fusion weights must be a dictionary")

            def _weight(name: str) -> float:
                value = weights_object.get(name)
                if not isinstance(value, (float, int)):
                    raise TypeError(f"fusion weight {name!r} must be numeric")
                return float(value)

            selected_weights = (
                _weight("solider"),
                _weight("siglip2"),
                _weight("dinov2"),
            )
            fused = _fuse(
                values,
                ("solider", "siglip2", "dinov2"),
                selected_weights,
                test,
            )
            fold_rows.append(
                {
                    "held_out_sequence": held_out,
                    "train_count": len(train),
                    "test_count": len(test),
                    "selected_weights": weights_object,
                    "test_metrics": _metrics(fused, target_indices[test]),
                }
            )
        cv[normalization] = fold_rows
    per_query_best = np.max(
        np.stack(
            [_rank(value, target_indices) <= 5 for value in arrays.values()],
            axis=0,
        ),
        axis=0,
    )
    result = {
        "schema_version": "cctv-chirla-score-fusion-analysis-v1",
        "dataset_status": metadata["dataset_status"],
        "protocol": metadata["protocol"],
        "query_count": len(target_indices),
        "identities": identities,
        "single_and_grid": combinations,
        "sequence_leave_one_out": cv,
        "oracle_any_single_model_recall_at_5": float(
            np.mean(np.asarray(per_query_best, dtype=np.float32))
        ),
        "oracle_any_single_model_hits": int(np.sum(per_query_best)),
        "oracle_warning": "oracle uses test outcomes and is not a deployable estimate",
    }
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(result["single_and_grid"], ensure_ascii=False))
    print(json.dumps(result["sequence_leave_one_out"], ensure_ascii=False))
    print(
        json.dumps(
            {
                "oracle_any_single_model_hits": result["oracle_any_single_model_hits"],
                "oracle_any_single_model_recall_at_5": result[
                    "oracle_any_single_model_recall_at_5"
                ],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
