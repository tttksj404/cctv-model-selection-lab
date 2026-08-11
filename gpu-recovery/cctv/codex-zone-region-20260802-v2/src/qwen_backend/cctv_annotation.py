from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PersonDetection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)


def select_primary_detection(
    detections: tuple[PersonDetection, ...],
) -> PersonDetection | None:
    if not detections:
        return None
    return max(detections, key=lambda detection: detection.area)
