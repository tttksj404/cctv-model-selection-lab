import json
from pathlib import Path

import pytest

from qwen_backend.config import Settings
from qwen_backend.distillation import DistillationSample
from qwen_backend.evaluation import StudentPrediction, evaluate_predictions
from qwen_backend.schemas import CandidateAttributes


def test_candidate_attributes_keep_texture_as_multi_label() -> None:
    attributes = CandidateAttributes(
        color="navy",
        clothing="jacket",
        texture=("solid", "slightly_glossy"),
    )

    assert attributes.texture == ("solid", "slightly_glossy")


def test_florence_settings_are_explicitly_configured() -> None:
    settings = Settings(
        florence_model_path=Path("/models/Florence-2-large"),
        florence_enabled=True,
        florence_max_new_tokens=128,
    )

    assert settings.florence_enabled is True
    assert settings.florence_max_new_tokens == 128


def test_qwen_review_has_a_separate_compact_token_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QWEN_REVIEW_MAX_NEW_TOKENS", "64")

    settings = Settings()

    assert settings.review_max_new_tokens == 64


def test_florence_label_round_trips_into_qwen_distillation_contract() -> None:
    sample = DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": "sample-florence-001",
            "imagePath": "candidate.jpg",
            "attributes": {
                "color": "navy",
                "clothing": "jacket",
                "texture": ["solid", "slightly_glossy"],
            },
            "decision": "review",
            "confidence": 0.84,
            "provenance": {
                "sourceKind": "florence",
                "teacherModel": "microsoft/Florence-2-large",
                "promptVersion": "florence-attributes-v1",
                "sourceHash": "0" * 64,
            },
        }
    )

    assert sample.attributes.texture == ("solid", "slightly_glossy")
    assert sample.provenance.source_kind == "florence"


def test_attribute_evaluation_reports_texture_accuracy() -> None:
    reference = DistillationSample.model_validate(
        {
            "schemaVersion": "distillation-v1",
            "sampleId": "sample-001",
            "imagePath": "candidate.jpg",
            "attributes": {"color": "navy", "texture": ["solid"]},
            "decision": "match",
            "confidence": 0.9,
            "provenance": {
                "sourceKind": "human",
                "teacherModel": "human-review",
                "promptVersion": "manual-v1",
                "sourceHash": "0" * 64,
            },
        }
    )
    prediction = StudentPrediction(
        sampleId="sample-001",
        output='{"decision":"match","attributes":{"color":"navy","texture":["solid"]},"confidence":0.8}',
    )

    report = evaluate_predictions((reference,), (prediction,))

    assert report.texture_accuracy == 1


def test_attribute_head_config_keeps_teacher_and_split_policy_explicit() -> None:
    config_path = Path("training/attribute_head_config.json")
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["student"]["name"] == "nanoowl-clip"
    assert config["heads"]["texture"]["task"] == "multi_label"
    assert config["teacherSources"][0]["sourceKind"] == "florence"
    assert config["teacherSources"][1]["status"] == "pending_api_and_terms_review"
    assert config["splitPolicy"]["forbidAdjacentFramesAcrossSplits"] is True
