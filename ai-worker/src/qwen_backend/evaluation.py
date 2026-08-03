from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from .distillation import DistillationSample, read_distillation_samples
from .schemas import CandidateAttributes, Decision


class StudentPrediction(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    sample_id: str = Field(alias="sampleId", min_length=1)
    output: str = Field(min_length=1)


class StudentAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    decision: Decision
    attributes: CandidateAttributes
    confidence: float = Field(ge=0, le=1)


class EvaluationReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    total: int = Field(ge=0)
    json_valid: int = Field(ge=0)
    decision_correct: int = Field(ge=0)
    color_correct: int = Field(ge=0)
    clothing_correct: int = Field(ge=0)
    texture_correct: int = Field(ge=0)
    json_valid_rate: float = Field(ge=0, le=1)
    decision_accuracy: float = Field(ge=0, le=1)
    color_accuracy: float = Field(ge=0, le=1)
    clothing_accuracy: float = Field(ge=0, le=1)
    texture_accuracy: float = Field(ge=0, le=1)


def read_predictions(path: Path) -> tuple[StudentPrediction, ...]:
    predictions: list[StudentPrediction] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            predictions.append(StudentPrediction.model_validate_json(line))
        except ValueError as error:
            raise ValueError(f"invalid prediction at {path}:{line_number}: {error}") from error
    return tuple(predictions)


def evaluate_predictions(
    references: tuple[DistillationSample, ...],
    predictions: tuple[StudentPrediction, ...],
) -> EvaluationReport:
    reference_by_id = {sample.sample_id: sample for sample in references}
    total = len(references)
    json_valid = 0
    decision_correct = 0
    color_correct = 0
    clothing_correct = 0
    texture_correct = 0

    for prediction in predictions:
        reference = reference_by_id.get(prediction.sample_id)
        if reference is None:
            continue
        try:
            answer = StudentAnswer.model_validate_json(prediction.output)
        except ValueError:
            continue
        json_valid += 1
        decision_correct += answer.decision == reference.decision
        color_correct += answer.attributes.color == reference.attributes.color
        clothing_correct += answer.attributes.clothing == reference.attributes.clothing
        texture_correct += answer.attributes.texture == reference.attributes.texture

    denominator = max(total, 1)
    return EvaluationReport(
        total=total,
        json_valid=json_valid,
        decision_correct=decision_correct,
        color_correct=color_correct,
        clothing_correct=clothing_correct,
        texture_correct=texture_correct,
        json_valid_rate=json_valid / denominator,
        decision_accuracy=decision_correct / denominator,
        color_accuracy=color_correct / denominator,
        clothing_accuracy=clothing_correct / denominator,
        texture_accuracy=texture_correct / denominator,
    )


def evaluate_files(reference_path: Path, prediction_path: Path) -> EvaluationReport:
    references = read_distillation_samples(reference_path)
    predictions = read_predictions(prediction_path)
    return evaluate_predictions(references, predictions)


def write_report(report: EvaluationReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
