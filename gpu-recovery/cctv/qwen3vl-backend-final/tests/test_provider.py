from pathlib import Path

from qwen_backend.config import Settings
from qwen_backend.providers import MockProvider, Qwen3VLProvider
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
    assert result.decision == "match"
    assert result.attributes.color == "red"
    assert result.model_version == "qwen3vl-mock-0.1"


def test_qwen_provider_is_lazy() -> None:
    provider = Qwen3VLProvider(Settings(provider="qwen"))
    assert provider.model_loaded is False
