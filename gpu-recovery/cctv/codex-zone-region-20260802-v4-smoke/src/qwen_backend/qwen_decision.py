from __future__ import annotations

from .config import Settings
from .decision_engine import decision_candidate_from_qwen
from .decision_gate import decide_candidates_for_retrieval_only_api
from .decision_schemas import (
    DecisionCandidate,
    DecisionRequest,
    DecisionResponse,
    QwenDecisionRequest,
)
from .providers import AnalysisProvider
from .schemas import CandidateAnalysisRequest, validate_local_image


def decide_with_qwen_candidates(
    request: QwenDecisionRequest,
    provider: AnalysisProvider,
    settings: Settings,
) -> DecisionResponse:
    enriched_candidates: list[DecisionCandidate] = []
    for candidate in request.candidates:
        image_path = validate_local_image(candidate.image_path, settings.image_root)
        analysis = provider.analyze(
            CandidateAnalysisRequest(
                caseId=request.case_id,
                cameraId=candidate.camera_id,
                trackId=candidate.track_id,
                imagePath=str(image_path),
                searchCondition=candidate.search_condition,
            )
        )
        enriched_candidates.append(
            decision_candidate_from_qwen(candidate, analysis, request.case_id)
        )
    return decide_candidates_for_retrieval_only_api(
        DecisionRequest(
            caseId=request.case_id,
            priority=request.priority,
            candidates=tuple(enriched_candidates),
        )
    )
