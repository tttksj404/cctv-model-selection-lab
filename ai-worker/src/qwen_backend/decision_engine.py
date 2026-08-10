from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .decision_schemas import (
    Decision,
    DecisionCandidate,
    DecisionPolicy,
    DecisionRequest,
    DecisionResponse,
    Escalation,
    Priority,
    QwenDecisionCandidate,
    RankedCandidate,
)
from .schemas import CandidateAnalysisResponse

_WEIGHTS: Final = (
    ("embedded_clip_score", 0.25),
    ("historical_retrieval_score", 0.20),
    ("attribute_consistency_score", 0.25),
    ("qwen_semantic_score", 0.10),
    ("track_consistency", 0.10),
    ("temporal_consistency", 0.06),
    ("spatial_consistency", 0.04),
)
_DEFAULT_POLICY: Final = DecisionPolicy()
_MAX_RETURNED_CANDIDATES: Final = 20


class DecisionEvidenceMismatch(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class _ScoredCandidate:
    candidate: DecisionCandidate
    score: float
    coverage: float
    reasons: tuple[str, ...]


def with_qwen_evidence(
    candidate: DecisionCandidate,
    analysis: CandidateAnalysisResponse,
    *,
    case_id: str | None = None,
) -> DecisionCandidate:
    if analysis.camera_id != candidate.camera_id or analysis.track_id != candidate.track_id:
        raise DecisionEvidenceMismatch("Qwen evidence does not match candidate camera or track")
    if case_id is not None and analysis.case_id != case_id:
        raise DecisionEvidenceMismatch("Qwen evidence does not match decision case")
    semantic_score = (
        analysis.semantic_match_score
        if analysis.semantic_match_score is not None
        else analysis.confidence
    )
    return candidate.model_copy(
        update={
            "qwen_semantic_score": semantic_score,
            "qwen_confidence": analysis.confidence,
        }
    )


def decision_candidate_from_qwen(
    candidate: QwenDecisionCandidate,
    analysis: CandidateAnalysisResponse,
    case_id: str,
) -> DecisionCandidate:
    base_candidate = DecisionCandidate.model_validate(
        candidate.model_dump(exclude={"image_path", "search_condition"})
    )
    return with_qwen_evidence(base_candidate, analysis, case_id=case_id)


def review_on_provider_failure(case_id: str, priority: Priority, reason: str) -> DecisionResponse:
    return DecisionResponse(
        caseId=case_id,
        decision="review",
        scoreMargin=0.0,
        escalation=_escalation(priority, "review"),
        reasons=(reason,),
        rankedCandidates=(),
    )


def _score_candidate(candidate: DecisionCandidate, conflict_range: float) -> _ScoredCandidate:
    weighted_score = 0.0
    available_weight = 0.0
    model_scores: list[float] = []
    reasons: list[str] = []

    for field_name, weight in _WEIGHTS:
        value = getattr(candidate, field_name)
        if value is None:
            continue
        if field_name == "qwen_semantic_score":
            value *= candidate.qwen_confidence
        weighted_score += value * weight
        available_weight += weight
        if field_name.endswith("score"):
            raw_value = getattr(candidate, field_name)
            if raw_value is not None:
                model_scores.append(raw_value)

    coverage = available_weight
    averaged_score = weighted_score / available_weight if available_weight else 0.0
    quality_factor = 0.70 + (0.30 * candidate.image_quality)
    score = max(0.0, min(1.0, averaged_score * (0.65 + (0.35 * coverage)) * quality_factor))

    if candidate.embedded_clip_score is None:
        reasons.append("missing_embedded_score")
    if candidate.historical_retrieval_score is None:
        reasons.append("missing_historical_score")
    if candidate.qwen_semantic_score is None:
        reasons.append("missing_qwen_score")
    if candidate.image_quality < 0.50:
        reasons.append("poor_image_quality")
    if candidate.observed_frames < 3:
        reasons.append("short_track")
    if model_scores and max(model_scores) - min(model_scores) >= conflict_range:
        reasons.append("model_disagreement")

    return _ScoredCandidate(candidate, score, coverage, tuple(reasons))


def _ranked_candidate(item: _ScoredCandidate, rank: int) -> RankedCandidate:
    return RankedCandidate(
        candidateId=item.candidate.candidate_id,
        trackId=item.candidate.track_id,
        cameraId=item.candidate.camera_id,
        identityGroupId=item.candidate.identity_group_id,
        rank=rank,
        score=round(item.score, 6),
        evidenceCoverage=round(item.coverage, 6),
        reasons=item.reasons,
    )


def _collapse_identity_groups(
    items: tuple[_ScoredCandidate, ...], conflict_range: float
) -> tuple[_ScoredCandidate, ...]:
    groups: dict[tuple[str, str], list[_ScoredCandidate]] = {}
    for item in items:
        key = (
            ("group", item.candidate.identity_group_id)
            if item.candidate.identity_group_id is not None
            else ("candidate", item.candidate.candidate_id)
        )
        groups.setdefault(key, []).append(item)

    collapsed: list[_ScoredCandidate] = []
    for group in groups.values():
        best = sorted(
            group,
            key=lambda item: (-item.score, item.candidate.candidate_id),
        )[0]
        if len(group) == 1:
            collapsed.append(best)
            continue
        mean_score = sum(item.score for item in group) / len(group)
        group_range = max(item.score for item in group) - min(item.score for item in group)
        group_reason = (
            "multi_view_conflict" if group_range >= conflict_range else "multi_view_confirmation"
        )
        merged_reasons = tuple(dict.fromkeys((*best.reasons, group_reason)))
        collapsed.append(
            _ScoredCandidate(
                candidate=best.candidate,
                score=(0.70 * best.score) + (0.30 * mean_score),
                coverage=max(item.coverage for item in group),
                reasons=merged_reasons,
            )
        )
    return tuple(collapsed)


def _escalation(priority: Priority, decision: Decision) -> Escalation:
    if priority in ("urgent", "critical"):
        return "urgent_operator_review"
    if decision == "review":
        return "operator_review"
    return "none"


def decide_candidates(request: DecisionRequest) -> DecisionResponse:
    if not request.candidates:
        return DecisionResponse(
            caseId=request.case_id,
            decision="reject",
            scoreMargin=0.0,
            escalation=_escalation(request.priority, "reject"),
            reasons=("no_candidate",),
            rankedCandidates=(),
        )

    scored = tuple(
        _score_candidate(candidate, _DEFAULT_POLICY.conflict_range)
        for candidate in request.candidates
    )
    grouped = _collapse_identity_groups(scored, _DEFAULT_POLICY.conflict_range)
    ranked = tuple(sorted(grouped, key=lambda item: (-item.score, item.candidate.candidate_id)))
    top = ranked[0]
    second_score = ranked[1].score if len(ranked) > 1 else 0.0
    margin = max(0.0, top.score - second_score)
    reasons = list(top.reasons)

    ambiguous = len(ranked) > 1 and margin <= _DEFAULT_POLICY.min_margin
    insufficient = (
        top.coverage < _DEFAULT_POLICY.min_evidence_coverage
        or top.candidate.observed_frames < _DEFAULT_POLICY.min_observed_frames
    )
    conflicting = any(
        reason in top.reasons for reason in ("model_disagreement", "multi_view_conflict")
    )
    if ambiguous:
        reasons.append("ambiguous_top_candidates")
    if insufficient:
        reasons.append("insufficient_evidence")

    blocked_from_match = (
        ambiguous
        or insufficient
        or conflicting
        or any(
            reason in top.reasons
            for reason in (
                "missing_embedded_score",
                "missing_historical_score",
                "missing_qwen_score",
                "poor_image_quality",
            )
        )
    )
    if top.score >= _DEFAULT_POLICY.match_threshold and not blocked_from_match:
        decision: Decision = "match"
        selected_candidate_id = top.candidate.candidate_id
    elif top.score >= _DEFAULT_POLICY.review_threshold or blocked_from_match:
        decision = "review"
        selected_candidate_id = None
    else:
        decision = "reject"
        selected_candidate_id = None

    unique_reasons = tuple(dict.fromkeys(reasons))
    return DecisionResponse(
        caseId=request.case_id,
        decision=decision,
        selectedCandidateId=selected_candidate_id,
        scoreMargin=round(margin, 6),
        escalation=_escalation(request.priority, decision),
        reasons=unique_reasons,
        rankedCandidates=tuple(
            _ranked_candidate(item, rank)
            for rank, item in enumerate(ranked[:_MAX_RETURNED_CANDIDATES], start=1)
        ),
    )

