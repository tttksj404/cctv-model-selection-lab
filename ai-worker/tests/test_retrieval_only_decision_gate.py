from qwen_backend.decision_gate import decide_candidates_for_retrieval_only_api
from qwen_backend.decision_schemas import DecisionRequest


def test_runtime_gate_downgrades_high_confidence_match_until_promotion() -> None:
    request = DecisionRequest.model_validate(
        {
            "caseId": "case-retrieval-only",
            "candidates": [
                {
                    "candidateId": "candidate-a",
                    "trackId": "track-a",
                    "cameraId": "cam-1",
                    "embeddedClipScore": 0.99,
                    "historicalRetrievalScore": 0.99,
                    "attributeConsistencyScore": 0.99,
                    "qwenSemanticScore": 0.99,
                    "qwenConfidence": 0.99,
                    "trackConsistency": 0.99,
                    "temporalConsistency": 0.99,
                    "spatialConsistency": 0.99,
                    "imageQuality": 0.99,
                    "observedFrames": 20,
                },
                {
                    "candidateId": "candidate-b",
                    "trackId": "track-b",
                    "cameraId": "cam-1",
                    "embeddedClipScore": 0.10,
                    "historicalRetrievalScore": 0.10,
                    "attributeConsistencyScore": 0.10,
                    "qwenSemanticScore": 0.10,
                    "qwenConfidence": 0.99,
                    "trackConsistency": 0.10,
                    "temporalConsistency": 0.10,
                    "spatialConsistency": 0.10,
                    "imageQuality": 0.99,
                    "observedFrames": 20,
                },
            ],
        }
    )

    result = decide_candidates_for_retrieval_only_api(request)

    assert result.decision == "review"
    assert result.selected_candidate_id is None
    assert result.escalation == "operator_review"
    assert "automatic_match_disabled" in result.reasons
