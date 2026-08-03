import pytest
from auth_support import TEST_INTERNAL_HEADERS
from fastapi.testclient import TestClient

from qwen_backend.config import Settings
from qwen_backend.decision_engine import (
    DecisionEvidenceMismatch,
    decide_candidates,
    decision_candidate_from_qwen,
    with_qwen_evidence,
)
from qwen_backend.decision_schemas import (
    DecisionCandidate,
    DecisionPolicy,
    DecisionRequest,
    QwenDecisionCandidate,
)
from qwen_backend.main import create_app
from qwen_backend.schemas import CandidateAnalysisResponse, CandidateAttributes


def candidate(candidate_id: str, **scores: float | str) -> dict[str, float | str]:
    value: dict[str, float | str] = {
        "candidateId": candidate_id,
        "trackId": f"track-{candidate_id}",
        "cameraId": "cam-1",
    }
    value.update(scores)
    return value


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


def test_identity_group_representative_is_deterministic_on_tie() -> None:
    first = candidate(
        "a",
        identityGroupId="person-a",
        embeddedClipScore=0.90,
        historicalRetrievalScore=0.90,
        qwenSemanticScore=0.90,
        qwenConfidence=1.0,
        trackConsistency=0.90,
        temporalConsistency=0.90,
        spatialConsistency=0.90,
        imageQuality=0.90,
        observedFrames=8,
    )
    second = dict(first, candidateId="b", trackId="track-b")

    forward = decide_candidates(
        DecisionRequest(caseId="case-1", candidates=(first, second)),
    )
    reverse = decide_candidates(
        DecisionRequest(caseId="case-1", candidates=(second, first)),
    )

    assert forward.ranked_candidates[0].candidate_id == "a"
    assert reverse.ranked_candidates[0].candidate_id == "a"


def test_consistent_identity_group_is_collapsed_for_public_decision() -> None:
    request = DecisionRequest(
        caseId="case-1",
        candidates=(
            candidate(
                "a",
                identityGroupId="forged-group",
                    embeddedClipScore=0.91,
                    historicalRetrievalScore=0.88,
                    attributeConsistencyScore=0.91,
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
                    embeddedClipScore=0.90,
                    historicalRetrievalScore=0.88,
                    attributeConsistencyScore=0.90,
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

    assert result.decision == "match"
    assert len(result.ranked_candidates) == 1
    assert "multi_view_confirmation" in result.reasons


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


def test_missing_qwen_evidence_cannot_match_high_other_scores() -> None:
    result = decide_candidates(
        DecisionRequest(
            caseId="case-1",
            candidates=(
                candidate(
                    "a",
                    embeddedClipScore=0.99,
                    historicalRetrievalScore=0.98,
                    trackConsistency=0.99,
                    temporalConsistency=0.99,
                    spatialConsistency=0.99,
                    imageQuality=0.99,
                    observedFrames=12,
                ),
            ),
        )
    )

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert "missing_qwen_score" in result.reasons


def test_poor_image_quality_cannot_match_high_other_scores() -> None:
    result = decide_candidates(
        DecisionRequest(
            caseId="case-1",
            candidates=(
                candidate(
                    "a",
                    embeddedClipScore=0.99,
                    historicalRetrievalScore=0.98,
                    qwenSemanticScore=0.99,
                    qwenConfidence=0.99,
                    trackConsistency=0.99,
                    temporalConsistency=0.99,
                    spatialConsistency=0.99,
                    imageQuality=0.20,
                    observedFrames=12,
                ),
            ),
        )
    )

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert "poor_image_quality" in result.reasons


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


def test_candidate_count_is_bounded() -> None:
    request_data = tuple(candidate(str(index)) for index in range(257))

    with pytest.raises(ValueError):
        DecisionRequest(caseId="case-1", candidates=request_data)


def test_server_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError):
        DecisionPolicy(matchThreshold=0.60, reviewThreshold=0.80)


def test_empty_candidate_set_is_not_a_match() -> None:
    result = decide_candidates(DecisionRequest(caseId="case-1", candidates=()))

    assert result.decision == "reject"
    assert result.selected_candidate_id is None
    assert "no_candidate" in result.reasons


def test_scores_are_bounded_at_the_api_boundary() -> None:
    with pytest.raises(ValueError):
        DecisionRequest(
            caseId="case-1",
            candidates=(candidate("a", embeddedClipScore=1.1),),
        )


def test_qwen_analysis_is_converted_to_decision_evidence() -> None:
    candidate_input = DecisionCandidate(
        candidateId="a",
        trackId="track-a",
        cameraId="cam-1",
        embeddedClipScore=0.8,
    )
    qwen_result = CandidateAnalysisResponse(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-a",
        decision="review",
        attributes=CandidateAttributes(color="red"),
        confidence=0.72,
        semanticMatchScore=0.68,
        modelVersion="qwen-mock",
        latencyMs=1.0,
    )

    enriched = with_qwen_evidence(candidate_input, qwen_result)

    assert enriched.qwen_semantic_score == 0.68
    assert enriched.qwen_confidence == 0.72


def test_qwen_analysis_must_match_candidate_provenance() -> None:
    candidate_input = DecisionCandidate(
        candidateId="a",
        trackId="track-a",
        cameraId="cam-1",
        embeddedClipScore=0.8,
    )
    qwen_result = CandidateAnalysisResponse(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-other",
        decision="review",
        attributes=CandidateAttributes(color="red"),
        confidence=0.72,
        semanticMatchScore=0.68,
        modelVersion="qwen-mock",
        latencyMs=1.0,
    )

    with pytest.raises(DecisionEvidenceMismatch):
        with_qwen_evidence(candidate_input, qwen_result, case_id="case-1")


def test_qwen_candidate_adapter_preserves_case_and_track_identity() -> None:
    candidate_input = QwenDecisionCandidate(
        candidateId="a",
        trackId="track-a",
        cameraId="cam-1",
        imagePath="candidate.jpg",
    )
    qwen_result = CandidateAnalysisResponse(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-a",
        decision="match",
        attributes=CandidateAttributes(color="red"),
        confidence=0.92,
        semanticMatchScore=0.90,
        modelVersion="qwen-mock",
        latencyMs=1.0,
    )

    enriched = decision_candidate_from_qwen(candidate_input, qwen_result, "case-1")

    assert enriched.candidate_id == "a"
    assert enriched.qwen_semantic_score == 0.90


def test_decision_endpoint_returns_case_level_result() -> None:
    app = create_app(Settings(provider="mock"))
    with TestClient(app, headers=TEST_INTERNAL_HEADERS) as client:
        response = client.post(
            "/v1/candidates/decide",
            json={
                "caseId": "case-1",
                "candidates": [candidate("a", embeddedClipScore=0.8)],
            },
        )

    assert response.status_code == 200
    assert response.json()["decision"] == "review"
