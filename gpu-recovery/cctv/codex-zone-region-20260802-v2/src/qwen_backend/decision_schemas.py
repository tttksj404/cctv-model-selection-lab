from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .schemas import SearchCondition

Decision = Literal["match", "review", "reject"]
Priority = Literal["normal", "urgent", "critical"]
Escalation = Literal["none", "operator_review", "urgent_operator_review"]


class DecisionPolicyValidationError(ValueError):
    pass


class DecisionPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    match_threshold: float = Field(default=0.82, alias="matchThreshold", ge=0, le=1)
    review_threshold: float = Field(default=0.56, alias="reviewThreshold", ge=0, le=1)
    min_margin: float = Field(default=0.08, alias="minMargin", ge=0, le=1)
    min_evidence_coverage: float = Field(default=0.55, alias="minEvidenceCoverage", ge=0, le=1)
    min_observed_frames: int = Field(default=3, alias="minObservedFrames", ge=0)
    conflict_range: float = Field(default=0.35, alias="conflictRange", ge=0, le=1)

    @model_validator(mode="after")
    def validate_order(self) -> "DecisionPolicy":
        if self.review_threshold > self.match_threshold:
            raise DecisionPolicyValidationError("reviewThreshold must not exceed matchThreshold")
        return self


class DecisionCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    candidate_id: str = Field(alias="candidateId", min_length=1, max_length=80)
    track_id: str = Field(alias="trackId", min_length=1, max_length=80)
    camera_id: str = Field(alias="cameraId", min_length=1, max_length=80)
    identity_group_id: str | None = Field(default=None, alias="identityGroupId", max_length=80)
    embedded_clip_score: float | None = Field(default=None, alias="embeddedClipScore", ge=0, le=1)
    historical_retrieval_score: float | None = Field(
        default=None, alias="historicalRetrievalScore", ge=0, le=1
    )
    attribute_consistency_score: float | None = Field(
        default=None, alias="attributeConsistencyScore", ge=0, le=1
    )
    qwen_semantic_score: float | None = Field(default=None, alias="qwenSemanticScore", ge=0, le=1)
    qwen_confidence: float = Field(default=0, alias="qwenConfidence", ge=0, le=1)
    track_consistency: float = Field(default=0, alias="trackConsistency", ge=0, le=1)
    temporal_consistency: float = Field(default=0, alias="temporalConsistency", ge=0, le=1)
    spatial_consistency: float = Field(default=0, alias="spatialConsistency", ge=0, le=1)
    image_quality: float = Field(default=0, alias="imageQuality", ge=0, le=1)
    observed_frames: int = Field(default=0, alias="observedFrames", ge=0)


class RankedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    candidate_id: str = Field(alias="candidateId")
    track_id: str = Field(alias="trackId")
    camera_id: str = Field(alias="cameraId")
    identity_group_id: str | None = Field(default=None, alias="identityGroupId")
    rank: int = Field(ge=1)
    score: float = Field(ge=0, le=1)
    evidence_coverage: float = Field(alias="evidenceCoverage", ge=0, le=1)
    reasons: tuple[str, ...] = ()


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    case_id: str = Field(alias="caseId", min_length=1, max_length=80)
    priority: Priority = "normal"
    candidates: tuple[DecisionCandidate, ...] = Field(default_factory=tuple, max_length=256)


class QwenDecisionCandidate(DecisionCandidate):
    image_path: str = Field(alias="imagePath", min_length=1, max_length=500)
    search_condition: SearchCondition = Field(
        default_factory=SearchCondition, alias="searchCondition"
    )


class QwenDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    case_id: str = Field(alias="caseId", min_length=1, max_length=80)
    priority: Priority = "normal"
    candidates: tuple[QwenDecisionCandidate, ...] = Field(default_factory=tuple, max_length=20)


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    case_id: str = Field(alias="caseId")
    decision: Decision
    selected_candidate_id: str | None = Field(default=None, alias="selectedCandidateId")
    score_margin: float = Field(alias="scoreMargin", ge=0, le=1)
    escalation: Escalation
    reasons: tuple[str, ...] = ()
    ranked_candidates: tuple[RankedCandidate, ...] = Field(alias="rankedCandidates")
