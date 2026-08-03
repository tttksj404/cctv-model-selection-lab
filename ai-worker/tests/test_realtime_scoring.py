from dataclasses import replace

import numpy as np

from qwen_backend.realtime_color_scoring import color_match_score
from qwen_backend.realtime_models import (
    AppearanceProfile,
    AppearanceRequirements,
    AttributeEvidence,
    BoundingBox,
    DecisionBand,
    RealtimeMatch,
    TrackState,
)
from qwen_backend.realtime_scoring import (
    DecisionThresholds,
    evaluate_attributes,
    resolve_frame_ambiguity,
    update_track,
)


def test_decision_thresholds_reject_zero_or_negative_attribute_weights() -> None:
    for kwargs in (
        {"top_color_weight": -0.1},
        {
            "top_color_weight": 0.0,
            "bottom_color_weight": 0.0,
            "glasses_weight": 0.0,
            "hair_weight": 0.0,
            "upper_style_weight": 0.0,
            "holistic_weight": 0.0,
            "identity_weight": 0.0,
        },
    ):
        try:
            DecisionThresholds(**kwargs)
        except ValueError:
            continue
        raise AssertionError(f"invalid attribute weights were accepted: {kwargs}")


def test_default_profile_preserves_reported_appearance() -> None:
    # Given
    profile = AppearanceProfile.default_demo()

    # When
    description = profile.description_ko

    # Then
    assert description == "회색 반팔, 검은색 바지, 안경, 넘긴 머리"
    assert "gray short-sleeve shirt" in profile.clip_query_en


def test_candidate_requires_strong_total_and_required_colors() -> None:
    # Given
    evidence = AttributeEvidence(
        top_color=0.91,
        bottom_color=0.88,
        glasses=0.84,
        hair=0.90,
        upper_style=0.82,
        holistic=0.86,
    )

    # When
    decision = evaluate_attributes(evidence)

    # Then
    assert decision.band is DecisionBand.CANDIDATE
    assert decision.score >= 0.8


def test_candidate_is_blocked_when_required_top_color_is_missing() -> None:
    # Given
    evidence = AttributeEvidence(
        top_color=0.10,
        bottom_color=0.95,
        glasses=0.95,
        hair=0.95,
        upper_style=0.95,
        holistic=0.95,
    )

    # When
    decision = evaluate_attributes(evidence)

    # Then
    assert decision.band is DecisionBand.REVIEW
    assert decision.required_color_score == 0.10


def test_candidate_is_blocked_when_reported_hair_is_absent() -> None:
    evidence = AttributeEvidence(
        top_color=0.95,
        bottom_color=0.95,
        glasses=0.90,
        hair=0.05,
        upper_style=0.90,
        holistic=0.90,
    )

    decision = evaluate_attributes(evidence)

    assert decision.band is DecisionBand.REVIEW
    assert decision.required_semantic_score == 0.05


def test_candidate_is_blocked_when_required_semantic_evidence_favors_opposite() -> None:
    evidence = AttributeEvidence(
        top_color=0.95,
        bottom_color=0.95,
        glasses=0.90,
        hair=0.49,
        upper_style=0.90,
        holistic=0.90,
    )

    decision = evaluate_attributes(evidence)

    assert decision.band is DecisionBand.REVIEW
    assert decision.required_semantic_score == 0.49


def test_temporal_candidate_requires_three_consistent_observations() -> None:
    # Given
    evidence = AttributeEvidence(
        top_color=0.93,
        bottom_color=0.92,
        glasses=0.88,
        hair=0.91,
        upper_style=0.86,
        holistic=0.89,
    )

    # When
    first = update_track(None, evidence)
    second = update_track(first, evidence)
    third = update_track(second, evidence)

    # Then
    assert first.decision.band is DecisionBand.REVIEW
    assert second.decision.band is DecisionBand.REVIEW
    assert third.decision.band is DecisionBand.CANDIDATE


def test_color_match_score_distinguishes_gray_navy_and_black_regions() -> None:
    # Given
    navy_region = np.full((32, 24, 3), (90, 45, 25), dtype=np.uint8)
    gray_region = np.full((32, 24, 3), (92, 96, 98), dtype=np.uint8)
    black_region = np.full((32, 24, 3), (25, 25, 25), dtype=np.uint8)

    # When
    navy_score = color_match_score(navy_region, target="navy")
    gray_score = color_match_score(gray_region, target="gray")
    black_score = color_match_score(black_region, target="black")

    # Then
    assert navy_score >= 0.95
    assert gray_score >= 0.95
    assert black_score >= 0.95


def test_dark_neutral_region_cannot_match_gray_and_black_together() -> None:
    dark_neutral_region = np.full((32, 24, 3), (60, 60, 60), dtype=np.uint8)

    gray_score = color_match_score(dark_neutral_region, target="gray")
    black_score = color_match_score(dark_neutral_region, target="black")

    assert gray_score == 0.0
    assert black_score >= 0.95


def test_unobserved_pants_force_review_without_zero_score_penalty() -> None:
    evidence = AttributeEvidence(
        top_color=0.90,
        bottom_color=None,
        glasses=0.80,
        hair=0.85,
        upper_style=0.90,
        holistic=0.82,
    )

    decision = evaluate_attributes(evidence)

    assert decision.band is DecisionBand.REVIEW
    assert decision.required_color_score is None
    assert decision.score >= 0.80


def test_unobserved_current_required_attribute_forces_review() -> None:
    observed = AttributeEvidence(0.9, 0.8, 0.7, 0.75, 0.85, 0.8)
    occluded = AttributeEvidence(0.88, None, 0.72, 0.73, 0.82, 0.79)

    first = update_track(None, observed)
    second = update_track(first, occluded)

    assert second.evidence.bottom_color is None
    assert second.decision.band is DecisionBand.REVIEW


def test_unspecified_attributes_do_not_block_candidate() -> None:
    requirements = AppearanceRequirements(
        top_color=True,
        bottom_color=False,
        glasses=False,
        hair=False,
        upper_style=True,
        identity=False,
    )
    evidence = AttributeEvidence(
        top_color=0.92,
        bottom_color=None,
        glasses=None,
        hair=None,
        upper_style=0.88,
        holistic=0.90,
    )

    decision = evaluate_attributes(evidence, requirements=requirements)

    assert decision.band is DecisionBand.CANDIDATE


def test_solider_identity_gate_blocks_different_person() -> None:
    requirements = AppearanceRequirements(
        top_color=True,
        bottom_color=False,
        glasses=False,
        hair=False,
        upper_style=True,
        identity=True,
    )
    evidence = AttributeEvidence(
        top_color=0.92,
        bottom_color=None,
        glasses=None,
        hair=None,
        upper_style=0.88,
        holistic=0.90,
        identity=0.40,
    )

    decision = evaluate_attributes(evidence, requirements=requirements)

    assert decision.band is DecisionBand.REVIEW


def test_close_runner_up_downgrades_top_candidate_to_review() -> None:
    evidence = AttributeEvidence(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
    top_state = update_track(update_track(update_track(None, evidence), evidence), evidence)
    runner_up_state = TrackState(
        evidence=evidence,
        observations=3,
        decision=replace(top_state.decision, score=0.85),
    )
    top = RealtimeMatch(1, BoundingBox(0, 0, 100, 200), 0.9, top_state)
    runner_up = RealtimeMatch(2, BoundingBox(100, 0, 200, 200), 0.9, runner_up_state)

    resolved = resolve_frame_ambiguity((top, runner_up))

    assert resolved[0].state.decision.band is DecisionBand.REVIEW
    assert resolved[1].state.decision.band is DecisionBand.REVIEW


def test_exact_candidate_margin_is_still_ambiguous() -> None:
    evidence = AttributeEvidence(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
    top_state = update_track(update_track(update_track(None, evidence), evidence), evidence)
    runner_up_state = TrackState(
        evidence=evidence,
        observations=3,
        decision=replace(top_state.decision, score=0.82),
    )
    top_state = replace(
        top_state,
        decision=replace(top_state.decision, score=0.90),
    )
    top = RealtimeMatch(1, BoundingBox(0, 0, 100, 200), 0.9, top_state)
    runner_up = RealtimeMatch(2, BoundingBox(100, 0, 200, 200), 0.9, runner_up_state)

    resolved = resolve_frame_ambiguity((top, runner_up))

    assert resolved[0].state.decision.band is DecisionBand.REVIEW
    assert resolved[1].state.decision.band is DecisionBand.REVIEW


def test_lower_candidate_is_downgraded_when_higher_match_requires_review() -> None:
    evidence = AttributeEvidence(0.9, 0.9, 0.9, 0.9, 0.9, 0.9)
    candidate_state = update_track(
        update_track(update_track(None, evidence), evidence),
        evidence,
    )
    review_state = replace(
        candidate_state,
        decision=replace(
            candidate_state.decision,
            band=DecisionBand.REVIEW,
            score=0.90,
        ),
    )
    candidate_state = replace(
        candidate_state,
        decision=replace(candidate_state.decision, score=0.85),
    )
    review = RealtimeMatch(1, BoundingBox(0, 0, 100, 200), 0.9, review_state)
    candidate = RealtimeMatch(
        2,
        BoundingBox(100, 0, 200, 200),
        0.9,
        candidate_state,
    )

    resolved = resolve_frame_ambiguity((review, candidate))

    assert resolved[0].state.decision.band is DecisionBand.REVIEW
    assert resolved[1].state.decision.band is DecisionBand.REVIEW
