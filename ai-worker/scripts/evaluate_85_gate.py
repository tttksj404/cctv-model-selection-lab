"""Fail-closed evaluator for the 85% model-promotion target.

This deliberately keeps PA-100K attribute metrics separate from CCTV identity
metrics.  A proxy result can be useful during training, but it cannot pass the
project promotion gate unless an identity/track-heldout receipt is present.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, cast


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("root JSON value must be an object")
    return cast(dict[str, Any], value)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    return float(value)


def _evaluate_proxy(payload: dict[str, Any], target: float) -> tuple[bool, list[str]]:
    experiments = payload.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        return False, ["proxy experiments are missing"]
    scores: list[float] = []
    for index, experiment in enumerate(cast(list[Any], experiments)):
        if not isinstance(experiment, dict) or "testMA" not in experiment:
            continue
        scores.append(_number(experiment["testMA"], f"experiments[{index}].testMA"))
    if not scores:
        return False, ["no testMA was found"]
    best = max(scores)
    passed = best >= target
    return passed, [f"best PA-100K test mA={best:.4f}; target={target:.4f}"]


def _evaluate_project(payload: dict[str, Any], target: float) -> tuple[bool, list[str]]:
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        return False, ["identityGeneralization85Evidence is not true"]
    decision_map = cast(dict[str, Any], decision)
    if decision_map.get("identityGeneralization85Evidence") is not True:
        return False, ["identityGeneralization85Evidence is not true"]

    selected_test = payload.get("selectedTest")
    if not isinstance(selected_test, dict):
        return False, ["selectedTest receipt is missing"]
    selected_test_map = cast(dict[str, Any], selected_test)
    rank1 = _number(selected_test_map.get("knownRank1"), "selectedTest.knownRank1")
    recall5 = _number(selected_test_map.get("knownRecallAt5"), "selectedTest.knownRecallAt5")
    auto = _number(
        selected_test_map.get("automaticDecisionAccuracy"),
        "selectedTest.automaticDecisionAccuracy",
    )
    fmr = _number(
        selected_test_map.get("distractorFalseMatchRate"),
        "selectedTest.distractorFalseMatchRate",
    )
    known = int(selected_test_map.get("knownQueries", 0))
    distractors = int(selected_test_map.get("distractorQueries", 0))
    reasons = [
        f"Rank-1={rank1:.4f}",
        f"Recall@5={recall5:.4f}",
        f"auto={auto:.4f}",
        f"FMR={fmr:.4f}",
        f"known={known}",
        f"distractors={distractors}",
    ]
    passed = (
        rank1 >= target
        and recall5 >= 0.95
        and auto >= target
        and fmr <= 0.05
        and known >= 100
        and distractors >= 100
    )
    return passed, reasons


def _evaluate_track_proxy(
    payload: dict[str, Any], target: float, minimum_tracks: int
) -> tuple[bool, list[str]]:
    """Gate the video-aligned proxy without mislabeling it as project evidence."""

    if payload.get("datasetStatus") != "public-proxy-not-project-CCTV":
        return False, ["track proxy must be explicitly marked non-project CCTV"]
    if payload.get("metricUnit") != "persistent-query-track":
        return False, ["track proxy must use persistent-query-track as its metric unit"]
    counts = payload.get("counts")
    track_level = payload.get("trackLevel")
    if not isinstance(counts, dict) or not isinstance(track_level, dict):
        return False, ["track proxy counts or trackLevel receipt is missing"]
    counts_map = cast(dict[str, Any], counts)
    track_level_map = cast(dict[str, Any], track_level)
    tracks = int(counts_map.get("queryTracks", 0))
    recall5 = _number(track_level_map.get("recallAt5"), "trackLevel.recallAt5")
    reasons = [
        f"track Recall@5={recall5:.4f}",
        f"tracks={tracks}",
        f"target={target:.4f}",
        "project CCTV promotion remains separate",
    ]
    return recall5 >= target and tracks >= minimum_tracks, reasons


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--mode", choices=("proxy", "track-proxy", "project"), required=True)
    parser.add_argument("--target", type=float, default=0.85)
    parser.add_argument("--minimum-tracks", type=int, default=40)
    args = parser.parse_args()

    try:
        payload = _read_json(args.input)
        if args.mode == "proxy":
            passed, reasons = _evaluate_proxy(payload, args.target)
        elif args.mode == "track-proxy":
            passed, reasons = _evaluate_track_proxy(
                payload, args.target, args.minimum_tracks
            )
        else:
            passed, reasons = _evaluate_project(payload, args.target)
    except ValueError as exc:
        print(f"FAIL: {exc}")
        return 2

    print(("PASS" if passed else "FAIL") + " | " + "; ".join(reasons))
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
