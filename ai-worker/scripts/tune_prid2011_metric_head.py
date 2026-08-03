from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

import numpy as np

from scripts.prid2011_metric_head import (
    MetricHead,
    apply_metric_head,
    fit_kissme_head,
    with_alpha,
)
from scripts.prid2011_track_cache import load_track_cache
from scripts.prid2011_track_metrics import calibrate_open_set, evaluate_retrieval


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Tune a KISSME residual metric head on PRID train identities"
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    return parser.parse_args()


def _selection_key(metrics: dict[str, float]) -> tuple[float, ...]:
    return (
        metrics["known_rank1"],
        metrics["automatic_decision_accuracy"],
        -metrics["distractor_false_match_rate"],
        metrics["known_mrr"],
    )


def main() -> None:
    args = _parse_args()
    tracks = load_track_cache(args.track_cache)
    validation = [track for track in tracks if track.split == "validation"]
    test = [track for track in tracks if track.split == "test"]
    baseline_calibration = calibrate_open_set(validation)
    baseline = {
        "validation": asdict(
            evaluate_retrieval(validation, baseline_calibration)
        ),
        "test": asdict(evaluate_retrieval(test, baseline_calibration)),
    }

    candidates: list[dict[str, object]] = []
    best_key = (-1.0, -1.0, -1.0, -1.0)
    best_head: MetricHead | None = None
    best_calibration = None
    best_candidate: dict[str, object] | None = None
    for regularization in (1e-4, 1e-3, 1e-2, 1e-1):
        for dimension in (32, 64, 128):
            fitted = fit_kissme_head(tracks, regularization, dimension)
            for alpha in (0.25, 0.5, 0.75, 1.0):
                head = with_alpha(fitted, alpha)
                adapted_validation = apply_metric_head(validation, head)
                calibration = calibrate_open_set(adapted_validation)
                validation_metrics = asdict(
                    evaluate_retrieval(adapted_validation, calibration)
                )
                candidate: dict[str, object] = {
                    "regularization": regularization,
                    "requestedDimension": dimension,
                    "actualDimension": head.dimension,
                    "alpha": alpha,
                    "calibration": asdict(calibration),
                    "validationMetrics": validation_metrics,
                }
                candidates.append(candidate)
                key = _selection_key(validation_metrics)
                if key > best_key:
                    best_key = key
                    best_head = head
                    best_calibration = calibration
                    best_candidate = candidate
    if best_head is None or best_calibration is None or best_candidate is None:
        raise RuntimeError("metric-head search produced no candidate")

    adapted_test = apply_metric_head(test, best_head)
    adapted_test_metrics = asdict(
        evaluate_retrieval(adapted_test, best_calibration)
    )
    result = {
        "schemaVersion": "prid2011-kissme-head-v1",
        "selectionProtocol": "train identities fit; validation-only hyperparameter selection",
        "baseline": baseline,
        "selected": best_candidate,
        "testMetrics": adapted_test_metrics,
        "candidates": candidates,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(
        args.head_output,
        mean=best_head.mean,
        basis=best_head.basis,
        projection=best_head.projection,
        alpha=np.asarray(best_head.alpha),
        regularization=np.asarray(best_head.regularization),
        dimension=np.asarray(best_head.dimension),
    )
    print(json.dumps({"selected": best_candidate, "testMetrics": adapted_test_metrics}))


if __name__ == "__main__":
    main()
