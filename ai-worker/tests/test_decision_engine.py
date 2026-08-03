from qwen_backend.decision_engine import decide_candidates
from qwen_backend.decision_schemas import DecisionCandidate, DecisionRequest


def candidate(candidate_id: str, **scores: float | str) -> DecisionCandidate:
    value: dict[str, float | str] = {
        "candidateId": candidate_id,
        "trackId": f"track-{candidate_id}",
        "cameraId": "cam-1",
    }
    value.update(scores)
    return DecisionCandidate.model_validate(value)


def test_three_similar_candidates_are_sent_to_review() -> None:
    request = DecisionRequest(
        caseId="case-1",
        priority="normal",
        candidates=(
            candidate(
                "a",
                embeddedClipScore=0.91,
                historicalRetrievalScore=0.88,
                qwenSemanticScore=0.90,
                qwenConfidence=0.92,
                trackConsistency=0.90,
                temporalConsistency=0.89,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
            candidate(
                "b",
                embeddedClipScore=0.90,
                historicalRetrievalScore=0.89,
                qwenSemanticScore=0.90,
                qwenConfidence=0.91,
                trackConsistency=0.89,
                temporalConsistency=0.88,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
            candidate(
                "c",
                embeddedClipScore=0.89,
                historicalRetrievalScore=0.88,
                qwenSemanticScore=0.89,
                qwenConfidence=0.90,
                trackConsistency=0.88,
                temporalConsistency=0.87,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert "ambiguous_top_candidates" in result.reasons
    assert len(result.ranked_candidates) == 3


def test_clear_candidate_can_match_when_evidence_is_complete() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "a",
                embeddedClipScore=0.95,
                historicalRetrievalScore=0.94,
                qwenSemanticScore=0.96,
                qwenConfidence=0.95,
                trackConsistency=0.95,
                temporalConsistency=0.93,
                spatialConsistency=0.92,
                imageQuality=0.95,
                observedFrames=10,
            ),
            candidate(
                "b",
                embeddedClipScore=0.42,
                historicalRetrievalScore=0.40,
                qwenSemanticScore=0.35,
                qwenConfidence=0.70,
                trackConsistency=0.45,
                temporalConsistency=0.40,
                spatialConsistency=0.40,
                imageQuality=0.80,
                observedFrames=4,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "match"
    assert result.selected_candidate_id == "a"
    assert result.score_margin >= 0.10


def test_attribute_head_breaks_identity_score_tie() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "attribute-strong",
                embeddedClipScore=0.80,
                historicalRetrievalScore=0.80,
                attributeConsistencyScore=0.95,
                qwenSemanticScore=0.80,
                qwenConfidence=1.0,
                trackConsistency=0.80,
                temporalConsistency=0.80,
                spatialConsistency=0.80,
                imageQuality=0.95,
                observedFrames=8,
            ),
            candidate(
                "attribute-weak",
                embeddedClipScore=0.80,
                historicalRetrievalScore=0.80,
                attributeConsistencyScore=0.25,
                qwenSemanticScore=0.80,
                qwenConfidence=1.0,
                trackConsistency=0.80,
                temporalConsistency=0.80,
                spatialConsistency=0.80,
                imageQuality=0.95,
                observedFrames=8,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "match"
    assert result.selected_candidate_id == "attribute-strong"
    assert result.score_margin > 0.10


def test_attribute_score_without_qwen_stays_review_only() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "attribute-only",
                embeddedClipScore=0.98,
                historicalRetrievalScore=0.97,
                attributeConsistencyScore=0.98,
                trackConsistency=0.96,
                temporalConsistency=0.95,
                spatialConsistency=0.94,
                imageQuality=0.96,
                observedFrames=10,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert "missing_qwen_score" in result.reasons


def test_same_identity_group_is_not_counted_as_two_people() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "a-cam-1",
                identityGroupId="person-a",
                embeddedClipScore=0.95,
                historicalRetrievalScore=0.94,
                qwenSemanticScore=0.96,
                qwenConfidence=0.95,
                trackConsistency=0.95,
                temporalConsistency=0.93,
                spatialConsistency=0.92,
                imageQuality=0.95,
                observedFrames=10,
            ),
            candidate(
                "a-cam-2",
                identityGroupId="person-a",
                embeddedClipScore=0.90,
                historicalRetrievalScore=0.89,
                qwenSemanticScore=0.91,
                qwenConfidence=0.90,
                trackConsistency=0.90,
                temporalConsistency=0.88,
                spatialConsistency=0.90,
                imageQuality=0.90,
                observedFrames=8,
            ),
            candidate(
                "b-cam-1",
                embeddedClipScore=0.40,
                historicalRetrievalScore=0.38,
                qwenSemanticScore=0.35,
                qwenConfidence=0.70,
                trackConsistency=0.40,
                temporalConsistency=0.40,
                spatialConsistency=0.40,
                imageQuality=0.80,
                observedFrames=4,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "match"
    assert result.selected_candidate_id == "a-cam-1"
    assert len(result.ranked_candidates) == 2


def test_identity_group_conflict_is_blocked_on_public_decision() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "a",
                identityGroupId="forged-group",
                embeddedClipScore=0.91,
                historicalRetrievalScore=0.88,
                qwenSemanticScore=0.90,
                qwenConfidence=0.92,
                trackConsistency=0.90,
                temporalConsistency=0.89,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
            candidate(
                "b",
                identityGroupId="forged-group",
                embeddedClipScore=0.10,
                historicalRetrievalScore=0.10,
                qwenSemanticScore=0.10,
                qwenConfidence=0.50,
                trackConsistency=0.10,
                temporalConsistency=0.10,
                spatialConsistency=0.10,
                imageQuality=0.90,
                observedFrames=8,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "review"
    assert "multi_view_conflict" in result.reasons


def test_missing_teacher_evidence_fails_closed_to_review() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "a",
                embeddedClipScore=0.96,
                trackConsistency=0.90,
                temporalConsistency=0.90,
                spatialConsistency=0.90,
                imageQuality=0.30,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert "insufficient_evidence" in result.reasons


def test_critical_priority_escalates_ambiguous_case() -> None:
    request = DecisionRequest(
        caseId="case-1",
        priority="critical",
        candidates=(
            candidate(
                "a",
                embeddedClipScore=0.91,
                historicalRetrievalScore=0.88,
                qwenSemanticScore=0.90,
                qwenConfidence=0.92,
                trackConsistency=0.90,
                temporalConsistency=0.89,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
            candidate(
                "b",
                embeddedClipScore=0.90,
                historicalRetrievalScore=0.88,
                qwenSemanticScore=0.89,
                qwenConfidence=0.91,
                trackConsistency=0.89,
                temporalConsistency=0.88,
                spatialConsistency=0.80,
                imageQuality=0.90,
                observedFrames=8,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "review"
    assert result.escalation == "urgent_operator_review"


def test_critical_low_score_still_escalates_to_operator() -> None:
    request = DecisionRequest(
        caseId="case-1",
        priority="critical",
        candidates=(
            candidate(
                "a",
                embeddedClipScore=0.1,
                historicalRetrievalScore=0.1,
                qwenSemanticScore=0.1,
                qwenConfidence=0.9,
                trackConsistency=0.1,
                temporalConsistency=0.1,
                spatialConsistency=0.1,
                imageQuality=0.9,
                observedFrames=4,
            ),
        ),
    )

    result = decide_candidates(request)

    assert result.decision == "reject"
    assert result.escalation == "urgent_operator_review"
