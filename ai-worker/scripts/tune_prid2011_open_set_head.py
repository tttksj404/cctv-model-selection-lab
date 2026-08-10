from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import TypedDict

import numpy as np

from scripts.prid2011_open_set_features import (
    FEATURE_NAMES,
    OpenSetBatch,
    build_training_episodes,
    decision_metrics,
    extract_open_set_batch,
    select_threshold,
)
from scripts.prid2011_open_set_models import (
    LinearProbabilityHead,
    ProbabilityModel,
    TanhProbabilityHead,
)
from scripts.prid2011_track_cache import load_track_cache


class OpenSetSearchError(RuntimeError):
    pass


class CandidateResult(TypedDict):
    name: str
    threshold: float
    validationFeasible: bool
    validationMetrics: dict[str, int | float]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Fit a gallery-size-robust open-set head on PRID train identities and "
            "select it on validation identities"
        )
    )
    parser.add_argument("--track-cache", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--head-output", type=Path, required=True)
    parser.add_argument("--episodes", type=int, default=500)
    parser.add_argument("--seed", type=int, default=20260729)
    return parser.parse_args()


def _candidate_models(seed: int) -> dict[str, ProbabilityModel]:
    return {
        "linear-l2-0.001": LinearProbabilityHead(regularization=0.001),
        "linear-l2-0.01": LinearProbabilityHead(regularization=0.01),
        "tanh-h16-l2-0.001": TanhProbabilityHead(
            hidden_size=16,
            regularization=0.001,
            seed=seed,
        ),
        "tanh-h32-l2-0.01": TanhProbabilityHead(
            hidden_size=32,
            regularization=0.01,
            seed=seed + 1,
        ),
    }


def _fit_candidates(
    models: dict[str, ProbabilityModel],
    train_features: np.ndarray,
    train_labels: np.ndarray,
    validation_batch: OpenSetBatch,
) -> tuple[list[CandidateResult], str, ProbabilityModel, float]:
    candidates: list[CandidateResult] = []
    best: tuple[tuple[float, ...], str, ProbabilityModel, float] | None = None
    for name, model in models.items():
        model.fit(train_features, train_labels)
        probabilities = model.predict_proba(validation_batch.features)[:, 1]
        threshold, metrics, feasible = select_threshold(
            validation_batch, probabilities
        )
        key = (
            float(feasible),
            metrics.automatic_decision_accuracy,
            -metrics.distractor_false_match_rate,
            -metrics.false_reject_rate,
        )
        candidate: CandidateResult = {
            "name": name,
            "threshold": threshold,
            "validationFeasible": feasible,
            "validationMetrics": asdict(metrics),
        }
        candidates.append(candidate)
        if best is None or key > best[0]:
            best = (key, name, model, threshold)
    if best is None:
        raise OpenSetSearchError("open-set head search produced no candidate")
    return candidates, best[1], best[2], best[3]


def main() -> None:
    args = _parse_args()
    tracks = load_track_cache(args.track_cache)
    train_batch = build_training_episodes(tracks, args.episodes, args.seed)
    validation_batch = extract_open_set_batch(
        [track for track in tracks if track.split == "validation"]
    )
    test_batch = extract_open_set_batch(
        [track for track in tracks if track.split == "test"]
    )
    candidates, best_name, best_model, threshold = _fit_candidates(
        _candidate_models(args.seed),
        train_batch.features,
        (train_batch.known & train_batch.top1_correct).astype(np.int32),
        validation_batch,
    )
    probabilities = best_model.predict_proba(test_batch.features)[:, 1]
    test_metrics = decision_metrics(test_batch, probabilities >= threshold)
    selected = next(item for item in candidates if item["name"] == best_name)
    result = {
        "schemaVersion": "prid2011-open-set-head-v1",
        "status": "valid",
        "selectionProtocol": (
            "synthetic episodes use train identities only; model and threshold "
            "selected on validation identities; sealed test evaluated once"
        ),
        "promotionContract": {
            "crossCamera": True,
            "identityDisjoint": True,
            "sealedTest": True,
            "thresholdSelectedOnValidationOnly": True,
            "projectCctvEvidence": False,
        },
        "featureNames": FEATURE_NAMES,
        "trainingRows": len(train_batch.features),
        "validationRows": len(validation_batch.features),
        "testRows": len(test_batch.features),
        "selected": selected,
        "candidates": candidates,
        "testMetrics": asdict(test_metrics),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    serialized_state = {
        key: value.tolist() for key, value in best_model.state().items()
    }
    head_payload = json.dumps(
        {
            "schemaVersion": "prid2011-open-set-head-v1",
            "featureNames": FEATURE_NAMES,
            "threshold": threshold,
            "state": serialized_state,
        },
        sort_keys=True,
    )
    args.head_output.parent.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(args.head_output, payload=np.asarray(head_payload))
    print(json.dumps({"selected": selected, "testMetrics": asdict(test_metrics)}))


if __name__ == "__main__":
    main()

