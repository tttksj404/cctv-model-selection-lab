from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from itertools import pairwise, product
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

PAIR_SCHEMA_VERSION = "eyesonu-orchestration-pair-evidence-v2"
RESULT_SCHEMA_VERSION = "eyesonu-orchestration-experiment-v2"


class ExperimentModel(BaseModel):
    model_config: ClassVar[ConfigDict] = ConfigDict(
        alias_generator=to_camel,
        extra="forbid",
        frozen=True,
        populate_by_name=True,
    )


class PairScoreRow(ExperimentModel):
    schema_version: Literal["eyesonu-orchestration-pair-evidence-v2"] = PAIR_SCHEMA_VERSION
    protocol: Literal["same_camera_track_heldout", "cross_camera_event_heldout"]
    query_track_id: str = Field(min_length=1, max_length=200)
    query_identity: str = Field(min_length=1, max_length=200)
    query_known: bool
    query_case_id: str = Field(min_length=1, max_length=200)
    query_video_id: str = Field(min_length=1, max_length=200)
    query_event_group_id: str = Field(min_length=1, max_length=200)
    query_timestamp_ms: int = Field(ge=0)
    query_camera: str = Field(min_length=1, max_length=200)
    gallery_track_id: str = Field(min_length=1, max_length=200)
    gallery_identity: str = Field(min_length=1, max_length=200)
    gallery_case_id: str = Field(min_length=1, max_length=200)
    gallery_video_id: str = Field(min_length=1, max_length=200)
    gallery_event_group_id: str = Field(min_length=1, max_length=200)
    gallery_timestamp_ms: int = Field(ge=0)
    gallery_camera: str = Field(min_length=1, max_length=200)
    split: Literal["validation", "test"]
    clip_score: float | None = Field(default=None, ge=0.0, le=1.0)
    solider_score: float | None = Field(default=None, ge=0.0, le=1.0)
    par_score: float | None = Field(default=None, ge=0.0, le=1.0)
    qwen_score: float | None = Field(default=None, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_model_evidence(self) -> PairScoreRow:
        if all(
            value is None
            for value in (self.clip_score, self.solider_score, self.par_score, self.qwen_score)
        ):
            raise ValueError("at least one model score is required")
        if self.query_track_id == self.gallery_track_id:
            raise ValueError("query and gallery track IDs must differ")
        return self


class FusionWeights(ExperimentModel):
    clip: float = Field(ge=0.0, le=1.0)
    solider: float = Field(ge=0.0, le=1.0)
    par: float = Field(ge=0.0, le=1.0)
    qwen: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def require_weight(self) -> FusionWeights:
        if sum((self.clip, self.solider, self.par, self.qwen)) <= 0.0:
            raise ValueError("at least one fusion weight must be positive")
        return self


class MetricSet(ExperimentModel):
    query_tracks: int = Field(ge=0)
    known_queries: int = Field(ge=0)
    distractor_queries: int = Field(ge=0)
    known_rank1: float = Field(ge=0.0, le=1.0)
    known_recall_at5: float = Field(ge=0.0, le=1.0)
    known_mrr: float = Field(ge=0.0, le=1.0)
    distractor_false_match_rate: float = Field(ge=0.0, le=1.0)
    false_reject_rate: float = Field(ge=0.0, le=1.0)
    automatic_decision_accuracy: float = Field(ge=0.0, le=1.0)
    score_threshold: float
    margin_threshold: float
    hard_negative_count: int = Field(ge=0)


class ArmResult(ExperimentModel):
    name: str = Field(min_length=1, max_length=100)
    weights: FusionWeights
    validation: MetricSet


class PromotionGate(ExperimentModel):
    required_known_queries: int = Field(gt=0)
    required_distractor_queries: int = Field(gt=0)
    known_queries: int = Field(ge=0)
    distractor_queries: int = Field(ge=0)
    eligible: bool
    passed: bool
    reasons: tuple[str, ...]


class ExperimentResult(ExperimentModel):
    schema_version: Literal["eyesonu-orchestration-experiment-v2"] = RESULT_SCHEMA_VERSION
    status: Literal["completed", "invalid"]
    data_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    row_count: int = Field(ge=0)
    validation_row_count: int = Field(ge=0)
    test_row_count: int = Field(ge=0)
    rounds: int = Field(ge=1)
    arm_results: tuple[ArmResult, ...]
    selected_arm: str | None
    selected_weights: FusionWeights | None
    selected_validation: MetricSet | None
    selected_test: MetricSet | None
    hard_negatives_mined: int = Field(ge=0)
    promotion_gate: PromotionGate


@dataclass(frozen=True, slots=True)
class _QueryOutcome:
    query_track_id: str
    known: bool
    correct_rank: int | None
    top1_correct: bool
    score: float
    margin: float
    accepted: bool


@dataclass(frozen=True, slots=True)
class _Arm:
    name: str
    weights: FusionWeights


def _fingerprint(rows: Sequence[PairScoreRow]) -> str:
    payload = "\n".join(row.model_dump_json() for row in rows).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_pair_rows(rows: Sequence[PairScoreRow]) -> None:
    if not rows:
        raise ValueError("orchestration evidence is empty")
    pair_keys: set[tuple[str, str, str]] = set()
    query_splits: dict[str, str] = {}
    query_provenance: dict[str, tuple[str, ...]] = {}
    gallery_provenance: dict[str, tuple[str, ...]] = {}
    protocols = {row.protocol for row in rows}
    if len(protocols) != 1:
        raise ValueError("all evidence rows must use one evaluation protocol")
    for row in rows:
        pair_key = (row.split, row.query_track_id, row.gallery_track_id)
        if pair_key in pair_keys:
            raise ValueError(f"duplicate query/gallery pair: {pair_key}")
        pair_keys.add(pair_key)
        previous_split = query_splits.setdefault(row.query_track_id, row.split)
        if previous_split != row.split:
            raise ValueError(f"query track appears in multiple splits: {row.query_track_id}")
        current_query_provenance = (
            row.query_case_id,
            row.query_video_id,
            row.query_event_group_id,
            str(row.query_timestamp_ms),
            row.query_camera,
        )
        previous_query_provenance = query_provenance.setdefault(
            row.query_track_id, current_query_provenance
        )
        if previous_query_provenance != current_query_provenance:
            raise ValueError(f"query track has inconsistent provenance: {row.query_track_id}")
        current_gallery_provenance = (
            row.gallery_case_id,
            row.gallery_video_id,
            row.gallery_event_group_id,
            str(row.gallery_timestamp_ms),
            row.gallery_camera,
        )
        previous_gallery_provenance = gallery_provenance.setdefault(
            row.gallery_track_id, current_gallery_provenance
        )
        if previous_gallery_provenance != current_gallery_provenance:
            raise ValueError(f"gallery track has inconsistent provenance: {row.gallery_track_id}")
        if row.protocol == "cross_camera_event_heldout" and row.query_camera == row.gallery_camera:
            raise ValueError(
                "cross_camera_event_heldout requires query and gallery cameras to differ"
            )


def _score(row: PairScoreRow, weights: FusionWeights) -> float:
    values = (
        (weights.clip, row.clip_score),
        (weights.solider, row.solider_score),
        (weights.par, row.par_score),
        (weights.qwen, row.qwen_score),
    )
    available = [(weight, value) for weight, value in values if value is not None and weight > 0.0]
    if not available:
        return 0.0
    denominator = sum(weight for weight, _ in available)
    return sum(weight * value for weight, value in available) / denominator


def _outcomes(
    rows: Sequence[PairScoreRow],
    weights: FusionWeights,
    score_threshold: float,
    margin_threshold: float,
) -> list[_QueryOutcome]:
    grouped: dict[str, list[PairScoreRow]] = defaultdict(list)
    for row in rows:
        grouped[row.query_track_id].append(row)
    outcomes: list[_QueryOutcome] = []
    for query_track_id, candidates in sorted(grouped.items()):
        ranked = sorted(
            ((row, _score(row, weights)) for row in candidates),
            key=lambda item: (-item[1], item[0].gallery_track_id),
        )
        top_score = ranked[0][1]
        second_score = ranked[1][1] if len(ranked) > 1 else -1.0
        query = candidates[0]
        correct_rank = next(
            (
                index + 1
                for index, (row, _) in enumerate(ranked)
                if query.query_known and row.gallery_identity == query.query_identity
            ),
            None,
        )
        outcomes.append(
            _QueryOutcome(
                query_track_id=query_track_id,
                known=query.query_known,
                correct_rank=correct_rank,
                top1_correct=bool(correct_rank == 1),
                score=top_score,
                margin=top_score - second_score,
                accepted=(
                    top_score >= score_threshold and top_score - second_score >= margin_threshold
                ),
            )
        )
    return outcomes


def _threshold_values(values: Iterable[float], lower: float) -> tuple[float, ...]:
    unique = sorted(set(values))
    if not unique:
        return (lower,)
    midpoints = tuple((left + right) / 2.0 for left, right in pairwise(unique))
    return (lower, *midpoints, unique[-1] + 1e-6)


def _calibrate(rows: Sequence[PairScoreRow], weights: FusionWeights) -> tuple[float, float]:
    raw = _outcomes(rows, weights, -1.0, -1.0)
    if not raw:
        return -1.0, -1.0
    best_key = (-1.0, -1.0, -1.0, -1.0, -1.0)
    best = (-1.0, -1.0)
    for score_threshold in _threshold_values((item.score for item in raw), -1.0):
        for margin_threshold in _threshold_values((item.margin for item in raw), -1.0):
            accepted = [
                item.score >= score_threshold and item.margin >= margin_threshold for item in raw
            ]
            known = [item for item in raw if item.known]
            distractors = [item for item in raw if not item.known]
            auto = sum(
                (item.known and accept and item.top1_correct) or (not item.known and not accept)
                for item, accept in zip(raw, accepted, strict=True)
            ) / len(raw)
            false_matches = sum(
                not item.known and accept for item, accept in zip(raw, accepted, strict=True)
            ) / max(1, len(distractors))
            false_rejects = sum(
                item.known and not accept for item, accept in zip(raw, accepted, strict=True)
            ) / max(1, len(known))
            recall_at5 = sum(
                item.correct_rank is not None and item.correct_rank <= 5 for item in known
            ) / max(1, len(known))
            key = (auto, recall_at5, -false_matches, -false_rejects, -score_threshold)
            if key > best_key:
                best_key = key
                best = (score_threshold, margin_threshold)
    return best


def _metric_set(
    rows: Sequence[PairScoreRow], weights: FusionWeights, thresholds: tuple[float, float]
) -> MetricSet:
    score_threshold, margin_threshold = thresholds
    outcomes = _outcomes(rows, weights, score_threshold, margin_threshold)
    known = [item for item in outcomes if item.known]
    distractors = [item for item in outcomes if not item.known]
    hard_negatives = sum(
        (not item.known and item.accepted) or (item.known and not item.top1_correct)
        for item in outcomes
    )
    auto_correct = sum(
        (item.known and item.accepted and item.top1_correct)
        or (not item.known and not item.accepted)
        for item in outcomes
    )
    return MetricSet(
        query_tracks=len(outcomes),
        known_queries=len(known),
        distractor_queries=len(distractors),
        known_rank1=sum(item.top1_correct for item in known) / max(1, len(known)),
        known_recall_at5=sum(
            item.correct_rank is not None and item.correct_rank <= 5 for item in known
        )
        / max(1, len(known)),
        known_mrr=sum(1.0 / item.correct_rank for item in known if item.correct_rank is not None)
        / max(1, len(known)),
        distractor_false_match_rate=sum(item.accepted for item in distractors)
        / max(1, len(distractors)),
        false_reject_rate=sum(item.known and not item.accepted for item in outcomes)
        / max(1, len(known)),
        automatic_decision_accuracy=auto_correct / max(1, len(outcomes)),
        score_threshold=score_threshold,
        margin_threshold=margin_threshold,
        hard_negative_count=hard_negatives,
    )


def _selection_key(metrics: MetricSet) -> tuple[float, float, float, float, float]:
    return (
        metrics.known_recall_at5,
        metrics.automatic_decision_accuracy,
        metrics.known_rank1,
        -metrics.distractor_false_match_rate,
        -metrics.false_reject_rate,
    )


def _fixed_arms() -> tuple[_Arm, ...]:
    return (
        _Arm("clip_only", FusionWeights(clip=1.0, solider=0.0, par=0.0, qwen=0.0)),
        _Arm("solider_only", FusionWeights(clip=0.0, solider=1.0, par=0.0, qwen=0.0)),
        _Arm("par_only", FusionWeights(clip=0.0, solider=0.0, par=1.0, qwen=0.0)),
        _Arm("clip_solider_equal", FusionWeights(clip=0.5, solider=0.5, par=0.0, qwen=0.0)),
        _Arm("clip_solider_par", FusionWeights(clip=0.4, solider=0.4, par=0.2, qwen=0.0)),
        _Arm(
            "clip_solider_par_qwen_review",
            FusionWeights(clip=0.35, solider=0.4, par=0.15, qwen=0.1),
        ),
    )


def _loop_candidates(round_number: int, seed: FusionWeights) -> tuple[_Arm, ...]:
    step = 0.15 / max(1, round_number)
    values = tuple(sorted({max(0.0, min(1.0, seed.clip + offset * step)) for offset in (-1, 0, 1)}))
    solider_values = tuple(
        sorted({max(0.0, min(1.0, seed.solider + offset * step)) for offset in (-1, 0, 1)})
    )
    par_values = tuple(
        sorted({max(0.0, min(1.0, seed.par + offset * step)) for offset in (-1, 0, 1)})
    )
    qwen_values = tuple(
        sorted({max(0.0, min(1.0, seed.qwen + offset * step)) for offset in (-1, 0, 1)})
    )
    arms: list[_Arm] = []
    for index, (clip, solider, par, qwen) in enumerate(
        product(values, solider_values, par_values, qwen_values)
    ):
        if clip + solider + par + qwen <= 0.0:
            continue
        arms.append(
            _Arm(
                name=f"loop_r{round_number}_{index:03d}",
                weights=FusionWeights(clip=clip, solider=solider, par=par, qwen=qwen),
            )
        )
    return tuple(arms)


def _gate(
    test: MetricSet,
    required_known: int,
    required_distractors: int,
) -> PromotionGate:
    reasons: list[str] = []
    eligible = (
        test.known_queries >= required_known and test.distractor_queries >= required_distractors
    )
    if not eligible:
        reasons.append(
            f"insufficient held-out queries: known={test.known_queries}/{required_known}, "
            f"distractors={test.distractor_queries}/{required_distractors}"
        )
    if test.known_rank1 < 0.85:
        reasons.append(f"known Rank-1 below 0.85: {test.known_rank1:.4f}")
    if test.known_recall_at5 < 0.95:
        reasons.append(f"known Recall@5 below 0.95: {test.known_recall_at5:.4f}")
    if test.automatic_decision_accuracy < 0.85:
        reasons.append(
            f"automatic decision accuracy below 0.85: {test.automatic_decision_accuracy:.4f}"
        )
    if test.distractor_false_match_rate > 0.05:
        reasons.append(
            f"distractor false-match rate above 0.05: {test.distractor_false_match_rate:.4f}"
        )
    if test.false_reject_rate > 0.15:
        reasons.append(f"false-reject rate above 0.15: {test.false_reject_rate:.4f}")
    return PromotionGate(
        required_known_queries=required_known,
        required_distractor_queries=required_distractors,
        known_queries=test.known_queries,
        distractor_queries=test.distractor_queries,
        eligible=eligible,
        passed=not reasons,
        reasons=tuple(reasons),
    )


def run_experiment(
    rows: Sequence[PairScoreRow],
    *,
    rounds: int = 3,
    required_known_queries: int = 100,
    required_distractor_queries: int = 100,
) -> ExperimentResult:
    if rounds < 1:
        raise ValueError("rounds must be at least one")
    validate_pair_rows(rows)
    validation = tuple(row for row in rows if row.split == "validation")
    test = tuple(row for row in rows if row.split == "test")
    if not validation or not test:
        raise ValueError("both validation and test rows are required")

    fixed_arms = _fixed_arms()
    arm_results: list[ArmResult] = []
    for arm in fixed_arms:
        thresholds = _calibrate(validation, arm.weights)
        arm_results.append(
            ArmResult(
                name=arm.name,
                weights=arm.weights,
                validation=_metric_set(validation, arm.weights, thresholds),
            )
        )

    validation_by_name = {item.name: item.validation for item in arm_results}
    best_arm = max(
        (_Arm(item.name, item.weights) for item in arm_results),
        key=lambda arm: _selection_key(validation_by_name[arm.name]),
    )
    hard_negatives_mined = 0
    for round_number in range(1, rounds + 1):
        candidates = _loop_candidates(round_number, best_arm.weights)
        best_round = best_arm
        best_round_metric = _metric_set(
            validation,
            best_arm.weights,
            _calibrate(validation, best_arm.weights),
        )
        for candidate in candidates:
            metrics = _metric_set(
                validation,
                candidate.weights,
                _calibrate(validation, candidate.weights),
            )
            hard_negatives_mined = max(hard_negatives_mined, metrics.hard_negative_count)
            if _selection_key(metrics) > _selection_key(best_round_metric):
                best_round = candidate
                best_round_metric = metrics
        best_arm = best_round

    selected_thresholds = _calibrate(validation, best_arm.weights)
    selected_validation = _metric_set(validation, best_arm.weights, selected_thresholds)
    selected_test = _metric_set(test, best_arm.weights, selected_thresholds)
    gate = _gate(selected_test, required_known_queries, required_distractor_queries)
    return ExperimentResult(
        status="completed",
        data_fingerprint=_fingerprint(rows),
        row_count=len(rows),
        validation_row_count=len(validation),
        test_row_count=len(test),
        rounds=rounds,
        arm_results=tuple(arm_results),
        selected_arm=best_arm.name,
        selected_weights=best_arm.weights,
        selected_validation=selected_validation,
        selected_test=selected_test,
        hard_negatives_mined=max(hard_negatives_mined, selected_validation.hard_negative_count),
        promotion_gate=gate,
    )
