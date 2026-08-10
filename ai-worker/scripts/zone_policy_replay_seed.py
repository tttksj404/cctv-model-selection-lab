from __future__ import annotations

import random
from typing import Literal, TypeAlias

TargetState: TypeAlias = int | Literal["outside", "unknown"]


class ReplaySeedError(ValueError):
    pass


def target_state_from_rng(rng: random.Random, scenario: str) -> TargetState:
    sample = rng.random()
    if scenario in {"location_certain", "currently_inside"}:
        return rng.randint(1, 4)
    if scenario == "location_uncertain":
        if sample < 0.80:
            return rng.randint(1, 4)
        return "outside" if sample < 0.90 else "unknown"
    if scenario == "recording_only_or_outside":
        if sample < 0.20:
            return rng.randint(1, 4)
        return "outside" if sample < 0.70 else "unknown"
    raise ReplaySeedError(f"unsupported replay scenario: {scenario}")


def expected_target_state(cell_seed: int, scenario: str) -> TargetState:
    return target_state_from_rng(random.Random(cell_seed), scenario)


__all__ = ["ReplaySeedError", "TargetState", "expected_target_state", "target_state_from_rng"]

