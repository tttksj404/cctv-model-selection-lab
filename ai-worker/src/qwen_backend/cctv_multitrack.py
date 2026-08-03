from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class InvalidRepresentativeLimitError(ValueError):
    limit: int

    def __str__(self) -> str:
        return f"representative limit must be positive: {self.limit}"


@dataclass(frozen=True, slots=True)
class TrackObservation:
    frame_index: int
    timestamp_ms: int
    bbox: tuple[float, float, float, float]
    confidence: float


def format_track_id(video_id: str, tracker_id: int) -> str:
    return f"{video_id}-track-{tracker_id:04d}"


def select_representative_observations(
    observations: tuple[TrackObservation, ...],
    *,
    limit: int,
) -> tuple[TrackObservation, ...]:
    if limit <= 0:
        raise InvalidRepresentativeLimitError(limit)
    ordered = tuple(sorted(observations, key=lambda item: item.frame_index))
    if len(ordered) <= limit:
        return ordered
    if limit == 1:
        return (ordered[(len(ordered) - 1) // 2],)
    positions = tuple(round(index * (len(ordered) - 1) / (limit - 1)) for index in range(limit))
    return tuple(ordered[position] for position in positions)
