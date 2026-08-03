from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ZonePredictionMetrics:
    total: int
    correct: int
    accuracy: float
    wilson95_lower: float
    wilson95_upper: float
    gate: float
    passed: bool


def conditional_zone_probabilities(probabilities: Sequence[float]) -> tuple[float, ...]:
    if len(probabilities) != 4:
        raise ValueError("exactly four zone probabilities are required")
    values = tuple(float(value) for value in probabilities)
    if any(not math.isfinite(value) or value < 0.0 for value in values):
        raise ValueError("zone probabilities must be finite and non-negative")
    total = sum(values)
    if total <= 0.0:
        raise ValueError("zone probability mass must be positive")
    return tuple(value / total for value in values)


def wilson_interval(
    successes: int,
    total: int,
    z: float = 1.959963984540054,
) -> tuple[float, float]:
    if total <= 0 or successes < 0 or successes > total:
        raise ValueError("successes and total do not define a binomial sample")
    probability = successes / total
    denominator = 1.0 + (z * z / total)
    center = probability + (z * z / (2.0 * total))
    radius = z * math.sqrt(
        (probability * (1.0 - probability) + z * z / (4.0 * total)) / total
    )
    return (center - radius) / denominator, (center + radius) / denominator


def evaluate_zone_predictions(
    targets: Sequence[int],
    predictions: Sequence[int],
    *,
    gate: float = 0.85,
) -> ZonePredictionMetrics:
    if len(targets) == 0 or len(targets) != len(predictions):
        raise ValueError("targets and predictions must be non-empty and equally sized")
    if not 0.0 < gate < 1.0:
        raise ValueError("gate must be between zero and one")
    labels = (*targets, *predictions)
    if any(isinstance(value, bool) or value not in range(1, 5) for value in labels):
        raise ValueError("zone labels must be integers from one through four")
    pairs = zip(targets, predictions, strict=True)
    correct = sum(target == prediction for target, prediction in pairs)
    lower, upper = wilson_interval(correct, len(targets))
    return ZonePredictionMetrics(
        total=len(targets),
        correct=correct,
        accuracy=correct / len(targets),
        wilson95_lower=lower,
        wilson95_upper=upper,
        gate=gate,
        passed=lower >= gate,
    )


__all__ = [
    "ZonePredictionMetrics",
    "conditional_zone_probabilities",
    "evaluate_zone_predictions",
    "wilson_interval",
]
