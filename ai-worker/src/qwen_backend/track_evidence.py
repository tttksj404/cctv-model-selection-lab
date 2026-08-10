from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from math import exp

import numpy as np

from qwen_backend.video_tracks import TrackFrame


@dataclass(frozen=True, slots=True)
class TrackConsistency:
    """Quality signals derived from one ByteTrack track.

    These are not identity probabilities.  They measure whether a candidate is
    observed repeatedly and whether its box changes in a physically plausible
    way.  Keeping them separate from appearance scores prevents a long,
    jittery false track from looking like a high-confidence identity match.
    """

    temporal: float
    spatial: float


def track_consistency(frames: Sequence[TrackFrame]) -> TrackConsistency:
    if not frames:
        raise ValueError("track consistency requires at least one frame")
    return TrackConsistency(
        temporal=_temporal_consistency(frames),
        spatial=_spatial_consistency(frames),
    )


def _temporal_consistency(frames: Sequence[TrackFrame]) -> float:
    timestamps = sorted({frame.frame_offset_ms for frame in frames})
    if len(timestamps) < 2:
        # A single observation is useful for retrieval, but it is weak evidence
        # for a track-level decision and is intentionally not treated as 1.0.
        return 0.35
    gaps = np.diff(np.asarray(timestamps, dtype=np.float64))
    mean_gap = float(np.mean(gaps))
    if mean_gap <= 0.0:
        return 0.35
    coefficient_of_variation = float(np.std(gaps) / mean_gap)
    regularity = exp(-min(coefficient_of_variation, 6.0))
    observation_coverage = min(1.0, len(timestamps) / 5.0)
    return _clamp(0.25 + (0.45 * regularity) + (0.30 * observation_coverage))


def _spatial_consistency(frames: Sequence[TrackFrame]) -> float:
    if len(frames) < 2:
        return 0.50
    centers = np.asarray(
        [
            (
                (frame.left + frame.right) / 2.0,
                (frame.top + frame.bottom) / 2.0,
            )
            for frame in frames
        ],
        dtype=np.float64,
    )
    widths = np.asarray([max(1, frame.right - frame.left) for frame in frames], dtype=np.float64)
    heights = np.asarray([max(1, frame.bottom - frame.top) for frame in frames], dtype=np.float64)
    reference_size = max(1.0, float(np.median(np.hypot(widths, heights))))
    center_mean = np.mean(centers, axis=0)
    center_deviation = np.hypot(centers[:, 0] - center_mean[0], centers[:, 1] - center_mean[1])
    normalized_deviation = float(np.median(center_deviation) / reference_size)
    size_variation = float(
        np.median(np.abs(widths - np.median(widths)) / np.median(widths))
        + np.median(np.abs(heights - np.median(heights)) / np.median(heights))
    )
    return _clamp(exp(-min(normalized_deviation + size_variation, 6.0)))


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))

