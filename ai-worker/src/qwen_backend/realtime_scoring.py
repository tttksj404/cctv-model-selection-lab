from __future__ import annotations

import math
from dataclasses import dataclass, replace

from qwen_backend.realtime_models import (
    AppearanceRequirements,
    AttributeEvidence,
    DecisionBand,
    MatchDecision,
    RealtimeMatch,
    TrackState,
)


@dataclass(frozen=True, slots=True)
class DecisionThresholds:
    candidate: float = 0.70
    review: float = 0.52
    required_color: float = 0.45
    required_semantic: float = 0.55
    required_identity: float = 0.60
    stable_observations: int = 3
    smoothing_alpha: float = 0.35
    candidate_margin: float = 0.08
    top_color_weight: float = 0.24
    bottom_color_weight: float = 0.22
    glasses_weight: float = 0.16
    hair_weight: float = 0.14
    upper_style_weight: float = 0.14
    holistic_weight: float = 0.10
    identity_weight: float = 0.25

    def __post_init__(self) -> None:
        weights = (
            self.top_color_weight,
            self.bottom_color_weight,
            self.glasses_weight,
            self.hair_weight,
            self.upper_style_weight,
            self.holistic_weight,
            self.identity_weight,
        )
        if any(not math.isfinite(weight) or weight < 0.0 for weight in weights) or not sum(
            weights
        ):
            raise ValueError("attribute weights must contain at least one positive value")


DEFAULT_THRESHOLDS = DecisionThresholds()
DEFAULT_REQUIREMENTS = AppearanceRequirements.default_demo()


def _clamp(score: float) -> float:
    return min(1.0, max(0.0, score))


def evaluate_attributes(
    evidence: AttributeEvidence,
    thresholds: DecisionThresholds = DEFAULT_THRESHOLDS,
    requirements: AppearanceRequirements = DEFAULT_REQUIREMENTS,
) -> MatchDecision:
    weighted_evidence = (
        (evidence.top_color, thresholds.top_color_weight),
        (evidence.bottom_color, thresholds.bottom_color_weight),
        (evidence.glasses, thresholds.glasses_weight),
        (evidence.hair, thresholds.hair_weight),
        (evidence.upper_style, thresholds.upper_style_weight),
        (evidence.holistic, thresholds.holistic_weight),
        (evidence.identity, thresholds.identity_weight),
    )
    observed = tuple(
        (value, weight) for value, weight in weighted_evidence if value is not None
    )
    observed_weight = sum(weight for _, weight in observed)
    score = _clamp(
        sum(value * weight for value, weight in observed) / observed_weight
        if observed_weight
        else 0.0
    )
    required_colors = tuple(
        value
        for required, value in (
            (requirements.top_color, evidence.top_color),
            (requirements.bottom_color, evidence.bottom_color),
        )
        if required
    )
    required_semantics = tuple(
        value
        for required, value in (
            (requirements.glasses, evidence.glasses),
            (requirements.hair, evidence.hair),
            (requirements.upper_style, evidence.upper_style),
        )
        if required
    )
    required_color_score = (
        None
        if any(value is None for value in required_colors)
        else min((value for value in required_colors if value is not None), default=1.0)
    )
    required_semantic_score = (
        None
        if any(value is None for value in required_semantics)
        else min((value for value in required_semantics if value is not None), default=1.0)
    )
    identity_passes = (
        not requirements.identity
        or (
            evidence.identity is not None
            and evidence.identity >= thresholds.required_identity
        )
    )

    if (
        score >= thresholds.candidate
        and required_color_score is not None
        and required_color_score >= thresholds.required_color
        and required_semantic_score is not None
        and required_semantic_score >= thresholds.required_semantic
        and identity_passes
    ):
        band = DecisionBand.CANDIDATE
    elif required_color_score is None or required_semantic_score is None:
        band = DecisionBand.REVIEW
    elif score >= thresholds.review:
        band = DecisionBand.REVIEW
    else:
        band = DecisionBand.MISMATCH
    return MatchDecision(
        band=band,
        score=round(score, 4),
        required_color_score=(
            round(required_color_score, 4) if required_color_score is not None else None
        ),
        required_semantic_score=(
            round(required_semantic_score, 4)
            if required_semantic_score is not None
            else None
        ),
    )


def _smooth_value(previous: float | None, current: float | None, alpha: float) -> float | None:
    if current is None:
        return None
    if previous is None:
        return current
    return previous * (1.0 - alpha) + current * alpha


def _smooth(
    previous: AttributeEvidence,
    current: AttributeEvidence,
    alpha: float,
) -> AttributeEvidence:
    return AttributeEvidence(
        top_color=_smooth_value(previous.top_color, current.top_color, alpha),
        bottom_color=_smooth_value(previous.bottom_color, current.bottom_color, alpha),
        glasses=_smooth_value(previous.glasses, current.glasses, alpha),
        hair=_smooth_value(previous.hair, current.hair, alpha),
        upper_style=_smooth_value(previous.upper_style, current.upper_style, alpha),
        holistic=_smooth_value(previous.holistic, current.holistic, alpha),
        identity=_smooth_value(previous.identity, current.identity, alpha),
    )


def update_track(
    previous: TrackState | None,
    evidence: AttributeEvidence,
    thresholds: DecisionThresholds = DEFAULT_THRESHOLDS,
    requirements: AppearanceRequirements = DEFAULT_REQUIREMENTS,
) -> TrackState:
    smoothed = (
        evidence
        if previous is None
        else _smooth(previous.evidence, evidence, thresholds.smoothing_alpha)
    )
    observations = 1 if previous is None else previous.observations + 1
    decision = evaluate_attributes(smoothed, thresholds, requirements)
    if (
        decision.band is DecisionBand.CANDIDATE
        and observations < thresholds.stable_observations
    ):
        decision = MatchDecision(
            band=DecisionBand.REVIEW,
            score=decision.score,
            required_color_score=decision.required_color_score,
            required_semantic_score=decision.required_semantic_score,
        )
    return TrackState(
        evidence=smoothed,
        observations=observations,
        decision=decision,
    )


def resolve_frame_ambiguity(
    matches: tuple[RealtimeMatch, ...],
    thresholds: DecisionThresholds = DEFAULT_THRESHOLDS,
) -> tuple[RealtimeMatch, ...]:
    if len(matches) < 2:
        return matches
    top, runner_up = matches[:2]
    margin = round(
        top.state.decision.score - runner_up.state.decision.score,
        4,
    )
    has_candidate = any(
        match.state.decision.band is DecisionBand.CANDIDATE
        for match in matches
    )
    if not has_candidate:
        return matches
    if (
        top.state.decision.band is DecisionBand.CANDIDATE
        and margin > thresholds.candidate_margin
    ):
        return matches
    resolved: list[RealtimeMatch] = []
    for match in matches:
        if match.state.decision.band is DecisionBand.CANDIDATE:
            review_decision = replace(
                match.state.decision,
                band=DecisionBand.REVIEW,
            )
            review_state = replace(match.state, decision=review_decision)
            resolved.append(replace(match, state=review_state))
        else:
            resolved.append(match)
    return tuple(resolved)
