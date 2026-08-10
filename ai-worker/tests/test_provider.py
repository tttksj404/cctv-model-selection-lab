from pathlib import Path

import pytest
from pydantic import ValidationError

from qwen_backend.config import Settings
from qwen_backend.providers import (
    MockProvider,
    ModelAnalysisPayload,
    Qwen3VLProvider,
    QwenReviewPayload,
)
from qwen_backend.schemas import CandidateAnalysisRequest, SearchCondition


def request_for(path: Path) -> CandidateAnalysisRequest:
    return CandidateAnalysisRequest(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-1",
        image_path=str(path),
        search_condition=SearchCondition(color="red"),
    )


def test_mock_provider_is_deterministic(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    result = MockProvider().analyze(request_for(image))
    assert result.decision == "review"
    assert result.attributes.color == "red"
    assert result.semantic_match_score == 0.5
    assert result.model_version == "qwen3vl-mock-0.1"


def test_qwen_provider_is_lazy() -> None:
    provider = Qwen3VLProvider(Settings(provider="qwen"))
    assert provider.model_loaded is False


def test_qwen_provider_uses_the_existing_qwen3vl_loader_without_qwen_vl_utils(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import sys
    import types

    model_calls: list[tuple[Path, dict[str, object]]] = []
    processor_calls: list[tuple[Path, dict[str, object]]] = []

    class FakeProcessor:
        @classmethod
        def from_pretrained(cls, checkpoint: Path, **kwargs: object) -> "FakeProcessor":
            processor_calls.append((checkpoint, kwargs))
            return cls()

    class FakeModel:
        @classmethod
        def from_pretrained(cls, checkpoint: Path, **kwargs: object) -> "FakeModel":
            model_calls.append((checkpoint, kwargs))
            return cls()

        def eval(self) -> "FakeModel":
            return self

    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoProcessor = FakeProcessor
    fake_transformers.Qwen3VLForConditionalGeneration = FakeModel
    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)

    provider = Qwen3VLProvider(
        Settings(provider="qwen", model_path=tmp_path, model_version="legacy-qwen3vl")
    )
    provider._load()

    assert provider.model_loaded is True
    assert processor_calls == [(tmp_path, {"local_files_only": True})]
    assert model_calls[0][0] == tmp_path
    assert model_calls[0][1]["local_files_only"] is True


def test_model_payload_requires_strict_fields() -> None:
    with pytest.raises(ValidationError):
        ModelAnalysisPayload.model_validate({"decision": "review", "attributes": {}})


def test_qwen_review_payload_uses_only_the_compact_review_contract() -> None:
    payload = QwenReviewPayload.model_validate(
        {
            "decision": "review",
            "confidence": 0.8,
            "semantic_match_score": 0.7,
        }
    )

    assert payload.decision == "review"
    assert payload.semantic_match_score == 0.7
    with pytest.raises(ValidationError):
        QwenReviewPayload.model_validate(
            {
                "decision": "review",
                "confidence": 0.8,
                "semantic_match_score": 0.7,
                "attributes": {"color": "gray"},
            }
        )

