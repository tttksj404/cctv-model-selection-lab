from pathlib import Path

import pytest
from pydantic import ValidationError

from qwen_backend.schemas import (
    CandidateAnalysisRequest,
    CandidateAnalysisResponse,
    CandidateAttributes,
    SearchCondition,
)


def test_request_rejects_remote_image() -> None:
    with pytest.raises(ValidationError):
        CandidateAnalysisRequest(
            case_id="case-1",
            camera_id="cam-1",
            track_id="track-1",
            image_path="https://example.com/candidate.jpg",
        )


def test_response_serializes_backend_fields() -> None:
    response = CandidateAnalysisResponse(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-1",
        decision="match",
        attributes=CandidateAttributes(color="red", clothing="jacket", object_name="person"),
        confidence=0.9,
        modelVersion="qwen3vl-mock-0.1",
        latencyMs=1.2,
    )
    assert response.model_dump(by_alias=True)["modelVersion"] == "qwen3vl-mock-0.1"


def test_local_image_validation_is_extension_and_file_based(tmp_path: Path) -> None:
    image = tmp_path / "candidate.jpg"
    image.write_bytes(b"fixture")
    request = CandidateAnalysisRequest(
        case_id="case-1",
        camera_id="cam-1",
        track_id="track-1",
        image_path=str(image),
        search_condition=SearchCondition(color="red"),
    )
    assert request.image_path == str(image)
