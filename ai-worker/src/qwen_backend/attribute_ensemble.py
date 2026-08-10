from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

import cv2
import numpy as np
from numpy.typing import NDArray

from qwen_backend.realtime_color_scoring import color_match_score
from qwen_backend.track_evidence import track_consistency
from qwen_backend.video_tracks import TrackFrame

ColorName = Literal[
    "black",
    "blue",
    "brown",
    "gray",
    "green",
    "navy",
    "orange",
    "pink",
    "purple",
    "red",
    "white",
    "yellow",
]


_COLOR_ALIASES: Final[dict[ColorName, tuple[str, ...]]] = {
    "black": ("black", "검정", "검은", "검은색", "흑색"),
    "blue": ("blue", "파랑", "파란", "파란색", "청색"),
    "brown": ("brown", "갈색", "브라운"),
    "gray": ("gray", "grey", "회색", "그레이"),
    "green": ("green", "초록", "녹색", "초록색"),
    "navy": ("navy", "남색", "네이비"),
    "orange": ("orange", "주황", "주황색", "오렌지"),
    "pink": ("pink", "분홍", "분홍색", "핑크"),
    "purple": ("purple", "보라", "보라색", "퍼플"),
    "red": ("red", "빨강", "빨간", "빨간색", "적색"),
    "white": ("white", "흰", "하얀", "하얀색", "백색"),
    "yellow": ("yellow", "노랑", "노란", "노란색", "황색"),
}
_UPPER_MARKERS: Final[tuple[str, ...]] = (
    "상의",
    "윗옷",
    "상체",
    "셔츠",
    "티셔츠",
    "반팔",
    "shirt",
    "top",
    "upper",
    "jacket",
    "coat",
    "sweater",
    "hoodie",
)
_LOWER_MARKERS: Final[tuple[str, ...]] = (
    "하의",
    "바지",
    "치마",
    "반바지",
    "pants",
    "trousers",
    "shorts",
    "skirt",
    "bottom",
    "lower",
)


@dataclass(frozen=True, slots=True)
class SearchAttributes:
    """Attributes that are safe to use as candidate filters.

    The parser is deliberately conservative.  A color is a hard requirement
    only when it is near an upper- or lower-garment marker; a bare color in a
    free-form prompt is not silently assigned to a body part.
    """

    upper_color: ColorName | None = None
    lower_color: ColorName | None = None
    glasses: bool = False
    hair: bool = False
    upper_style: bool = False

    @property
    def has_color_requirement(self) -> bool:
        return self.upper_color is not None or self.lower_color is not None


@dataclass(frozen=True, slots=True)
class FrameAttributeScores:
    semantic: float
    upper_color: float | None
    lower_color: float | None
    fine_attribute: float | None
    identity: float | None
    quality: float
    par_attribute: float | None = None


@dataclass(frozen=True, slots=True)
class TrackAttributeScores:
    semantic: float
    required_color: float | None
    fine_attribute: float | None
    identity: float | None
    quality: float
    score: float
    par_attribute: float | None = None
    temporal: float = 0.35
    spatial: float = 0.50
    historical: float | None = None
    qwen: float | None = None


@dataclass(frozen=True, slots=True)
class EnsembleDecision:
    emit: bool
    score: float
    reason: str | None


def _positions(text: str, terms: Sequence[str]) -> tuple[int, ...]:
    return tuple(index for term in terms for index in _find_all(text, term))


def _find_all(text: str, term: str) -> tuple[int, ...]:
    starts: list[int] = []
    offset = 0
    while True:
        index = text.find(term, offset)
        if index < 0:
            return tuple(starts)
        starts.append(index)
        offset = index + max(1, len(term))


def _nearest_color(text: str, markers: Sequence[str]) -> ColorName | None:
    marker_positions = _positions(text, markers)
    if not marker_positions:
        return None
    best: tuple[int, int, ColorName] | None = None
    for color, aliases in _COLOR_ALIASES.items():
        for color_position in _positions(text, aliases):
            marker_position = min(marker_positions, key=lambda value: abs(value - color_position))
            distance = abs(marker_position - color_position)
            # English prompts normally put the color before the garment; Korean
            # prompts do both.  The second tuple item makes equal distances
            # deterministic without rejecting either word order.
            follows_marker = int(color_position > marker_position)
            candidate = (distance, follows_marker, color)
            if distance <= 32 and (best is None or candidate[:2] < best[:2]):
                best = candidate
    return best[2] if best is not None else None


def parse_search_attributes(prompt: str) -> SearchAttributes:
    text = " ".join(prompt.strip().lower().split())
    if not text:
        return SearchAttributes()
    return SearchAttributes(
        upper_color=_nearest_color(text, _UPPER_MARKERS),
        lower_color=_nearest_color(text, _LOWER_MARKERS),
        glasses=bool(re.search(r"안경|eyeglasses|glasses|spectacles|sunglasses", text)),
        hair=bool(re.search(r"머리|헤어|hair|hairstyle|헤어스타일", text)),
        upper_style=bool(
            re.search(
                r"반팔|긴팔|민소매|short[- ]?sleeve|long[- ]?sleeve|sleeveless|"
                r"jacket|coat|sweater|hoodie",
                text,
            )
        ),
    )


def _regions(crop_bgr: NDArray[np.uint8]) -> tuple[NDArray[np.uint8], ...]:
    height, width = crop_bgr.shape[:2]
    upper = crop_bgr[
        round(height * 0.16) : max(round(height * 0.62), 1),
        round(width * 0.10) : max(round(width * 0.90), 1),
    ]
    lower = crop_bgr[
        round(height * 0.52) : max(round(height * 0.98), 1),
        round(width * 0.16) : max(round(width * 0.84), 1),
    ]
    return crop_bgr, upper, lower


def color_scores(
    crop_bgr: NDArray[np.uint8],
    attributes: SearchAttributes,
) -> tuple[float | None, float | None]:
    """Return upper/lower ROI color scores for one tracked crop."""

    _, upper, lower = _regions(crop_bgr)
    upper_score = (
        color_match_score(upper, target=attributes.upper_color)
        if attributes.upper_color is not None
        else None
    )
    lower_score = (
        color_match_score(lower, target=attributes.lower_color)
        if attributes.lower_color is not None and crop_bgr.shape[0] >= crop_bgr.shape[1] * 1.3
        else None
    )
    return upper_score, lower_score


def _top_mean(values: Sequence[float], count: int = 3) -> float | None:
    finite = sorted((float(value) for value in values if np.isfinite(value)), reverse=True)
    if not finite:
        return None
    selected = finite[: max(1, min(count, len(finite)))]
    return float(sum(selected) / len(selected))


def aggregate_track_scores(
    rows: Sequence[FrameAttributeScores],
    attributes: SearchAttributes,
    *,
    top_frames: int = 3,
) -> TrackAttributeScores:
    if not rows:
        raise ValueError("track must contain at least one scored frame")
    ranked = sorted(rows, key=lambda row: row.semantic, reverse=True)
    selected = ranked[: max(1, min(top_frames, len(ranked)))]
    semantic = _top_mean([row.semantic for row in selected]) or 0.0
    upper = _top_mean([row.upper_color for row in selected if row.upper_color is not None])
    lower = _top_mean([row.lower_color for row in selected if row.lower_color is not None])
    required_colors = [score for score in (upper, lower) if score is not None]
    required_color = min(required_colors) if required_colors else None
    fine = _top_mean([row.fine_attribute for row in selected if row.fine_attribute is not None])
    par_attribute = _top_mean(
        [row.par_attribute for row in selected if row.par_attribute is not None]
    )
    identity = _top_mean([row.identity for row in selected if row.identity is not None])
    quality = _top_mean([row.quality for row in selected]) or 0.0

    weighted: list[tuple[float, float]] = []
    if identity is not None:
        weighted.append((identity, 0.45))
    weighted.append((semantic, 0.20 if identity is not None else 0.35))
    if required_color is not None:
        weighted.append((required_color, 0.25 if identity is not None else 0.45))
    if fine is not None:
        weighted.append((fine, 0.10 if identity is not None else 0.20))
    score = sum(value * weight for value, weight in weighted) / sum(
        weight for _, weight in weighted
    )
    return TrackAttributeScores(
        semantic=semantic,
        required_color=required_color,
        fine_attribute=fine,
        identity=identity,
        quality=quality,
        score=max(0.0, min(1.0, score)),
        par_attribute=par_attribute,
    )


def add_track_consistency(
    scores: TrackAttributeScores,
    frames: Sequence[TrackFrame],
) -> TrackAttributeScores:
    """Attach scale-free temporal and spatial evidence to a track aggregate."""

    consistency = track_consistency(frames)
    return replace(scores, temporal=consistency.temporal, spatial=consistency.spatial)


def fuse_track_scores(
    scores: TrackAttributeScores,
    *,
    historical: float | None = None,
    qwen: float | None = None,
) -> TrackAttributeScores:
    """Fuse available evidence while renormalizing missing optional signals.

    Missing identity/gallery/Qwen evidence is never converted to zero.  It is
    omitted from the denominator and remains visible in the returned object so
    the caller can keep the result in operator-review mode.
    """

    signals: list[tuple[float, float]] = [
        (scores.semantic, 0.16),
        (scores.temporal, 0.06),
        (scores.spatial, 0.04),
        (scores.quality, 0.04),
    ]
    if scores.required_color is not None:
        signals.append((scores.required_color, 0.18))
    if scores.par_attribute is not None:
        signals.append((scores.par_attribute, 0.20))
    elif scores.fine_attribute is not None:
        signals.append((scores.fine_attribute, 0.12))
    if scores.identity is not None:
        signals.append((scores.identity, 0.28))
    if historical is not None:
        signals.append((historical, 0.16))
    if qwen is not None:
        signals.append((qwen, 0.12))
    total_weight = sum(weight for _, weight in signals)
    if total_weight <= 0.0:
        raise ValueError("track fusion has no usable evidence")
    score = sum(value * weight for value, weight in signals) / total_weight
    return replace(
        scores,
        historical=historical,
        qwen=qwen,
        score=max(0.0, min(1.0, score)),
    )


def decide_track(
    scores: TrackAttributeScores,
    attributes: SearchAttributes,
    *,
    minimum_output_score: float,
    color_reject_threshold: float,
    similarity_threshold: float | None,
) -> EnsembleDecision:
    if attributes.has_color_requirement:
        if scores.required_color is None:
            return EnsembleDecision(False, scores.score, "required_color_unavailable")
        if scores.required_color < color_reject_threshold:
            return EnsembleDecision(False, scores.score, "required_color_mismatch")
    if similarity_threshold is not None and scores.score < similarity_threshold:
        return EnsembleDecision(False, scores.score, "server_similarity_threshold")
    if scores.score < minimum_output_score:
        return EnsembleDecision(False, scores.score, "below_candidate_floor")
    return EnsembleDecision(True, scores.score, None)


def crop_quality(crop_path: str | object) -> float:
    path = str(crop_path)
    image = cv2.imread(path, cv2.IMREAD_COLOR)
    if image is None or image.size == 0:
        return 0.0
    height, width = image.shape[:2]
    return max(0.0, min(1.0, width / 96.0) * min(1.0, height / 256.0))


def model_trace(statuses: Sequence[tuple[str, str]]) -> str:
    return "; ".join(f"{name}={status}" for name, status in statuses)

