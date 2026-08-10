from __future__ import annotations

from typing import assert_never

from .decision_engine import decide_candidates as score_candidates
from .decision_schemas import (
    DecisionRequest,
    DecisionResponse,
    Escalation,
    Priority,
)
from .schemas import CandidateAnalysisResponse


def _review_escalation(priority: Priority) -> Escalation:
    if priority == "normal":
        return "operator_review"
    if priority in ("urgent", "critical"):
        return "urgent_operator_review"
    assert_never(priority)


def decide_candidates_for_retrieval_only_api(request: DecisionRequest) -> DecisionResponse:
    result = score_candidates(request)
    if result.decision == "match":
        return DecisionResponse(
            caseId=result.case_id,
            decision="review",
            selectedCandidateId=None,
            scoreMargin=result.score_margin,
            escalation=_review_escalation(request.priority),
            reasons=tuple(dict.fromkeys((*result.reasons, "automatic_match_disabled"))),
            rankedCandidates=result.ranked_candidates,
        )
    if result.decision in ("review", "reject"):
        return result
    assert_never(result.decision)


def enforce_retrieval_only_analysis(
    result: CandidateAnalysisResponse,
) -> CandidateAnalysisResponse:
    if result.decision != "match":
        return result
    return result.model_copy(
        update={
            "decision": "review",
            "failure_reason": result.failure_reason or "automatic_match_disabled",
        }
    )

