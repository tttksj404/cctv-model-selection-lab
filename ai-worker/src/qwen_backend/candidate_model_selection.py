from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict


class ScoreComparison(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    baseline: float
    sonnet: float
    delta: float


class CheckpointReplay(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    cctv_proxy_group_heldout_mean: ScoreComparison


class SameRunAblation(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    requested_79_checkpoint_replay: CheckpointReplay


class ComparisonArms(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    same_run_sonnet_ablation: SameRunAblation


class PromotionGate(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    passed: bool


class SonnetComparison(BaseModel):
    model_config = ConfigDict(extra="ignore", frozen=True)

    schema_version: str
    arms: ComparisonArms
    promotion_gate: PromotionGate
    project_cctv_gate: PromotionGate


@dataclass(frozen=True, slots=True)
class CandidateModelDecision:
    retrieval_model: str
    selected_attribute_head: str
    sonnet_promoted: bool
    baseline_score: float
    sonnet_score: float
    observed_delta: float
    reason: str


def select_candidate_model(comparison_data: Mapping[str, object]) -> CandidateModelDecision:
    comparison = SonnetComparison.model_validate(comparison_data)
    score = (
        comparison.arms.same_run_sonnet_ablation.requested_79_checkpoint_replay
        .cctv_proxy_group_heldout_mean
    )
    sonnet_improved = (
        score.sonnet > score.baseline
        and score.delta > 0.0
        and comparison.promotion_gate.passed
        and comparison.project_cctv_gate.passed
    )
    if sonnet_improved:
        selected_head = "sonnet"
        reason = "Sonnet improved the same-protocol held-out score and passed both gates."
    else:
        selected_head = "baseline"
        reason = (
            "Sonnet did not improve the same-protocol held-out score with both promotion "
            "gates satisfied."
        )
    return CandidateModelDecision(
        retrieval_model="hybrid-solider-clip-v1",
        selected_attribute_head=selected_head,
        sonnet_promoted=sonnet_improved,
        baseline_score=score.baseline,
        sonnet_score=score.sonnet,
        observed_delta=score.delta,
        reason=reason,
    )
