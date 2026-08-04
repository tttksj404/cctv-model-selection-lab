from pathlib import Path

import pytest
from pydantic import ValidationError

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
    run_runtime,
)


class FixtureEngine:
    model_key = "fixture-hybrid-v1"

    def analyze(self, request: CandidateRuntimeRequest) -> CandidateRuntimeResponse:
        frame_path = request.output_dir / "frame-1250.jpg"
        crop_path = request.output_dir / "track-3.jpg"
        frame_path.write_bytes(b"frame")
        crop_path.write_bytes(b"crop")
        return CandidateRuntimeResponse(
            modelKey=self.model_key,
            candidates=(
                RuntimeCandidate(
                    candidateKey="track-3",
                    frameOffsetMs=1_250,
                    similarity=0.91,
                    framePath=frame_path,
                    cropPath=crop_path,
                    boundingBox=RuntimeBoundingBox(x=10, y=20, width=30, height=40),
                    attributeSummary="reference-image SOLIDER retrieval",
                ),
            ),
        )


def _request(tmp_path: Path) -> CandidateRuntimeRequest:
    video_path = tmp_path / "recording.mp4"
    reference_path = tmp_path / "reference.jpg"
    output_dir = tmp_path / "candidates"
    video_path.write_bytes(b"video")
    reference_path.write_bytes(b"reference")
    output_dir.mkdir()
    return CandidateRuntimeRequest(
        modelKey="fixture-hybrid-v1",
        jobId=71,
        caseId=11,
        searchConditionId=21,
        recordingId=31,
        cameraId=41,
        cameraName="Gate A",
        cameraAddress="Seoul",
        videoPath=video_path,
        referencePath=reference_path,
        outputDir=output_dir,
        prompt="red jacket and black backpack",
        exclusionPrompt=None,
        similarityThreshold=0.8,
        searchFromMs=1_000,
        searchToMs=5_000,
    )


def test_runtime_serializes_gpu_candidates_for_worker(tmp_path: Path) -> None:
    response = run_runtime(_request(tmp_path).model_dump_json(by_alias=True), FixtureEngine())

    parsed = CandidateRuntimeResponse.model_validate_json(response)

    assert parsed.model_key == "fixture-hybrid-v1"
    assert parsed.candidates[0].frame_path.read_bytes() == b"frame"
    assert parsed.candidates[0].crop_path.read_bytes() == b"crop"
    assert parsed.candidates[0].bounding_box.height == 40


def test_runtime_rejects_engine_model_identity_mismatch(tmp_path: Path) -> None:
    request = _request(tmp_path).model_copy(update={"model_key": "unexpected-model"})

    with pytest.raises(ValueError, match="model key"):
        run_runtime(request.model_dump_json(by_alias=True), FixtureEngine())


def test_runtime_rejects_remote_video_paths(tmp_path: Path) -> None:
    payload = _request(tmp_path).model_dump(by_alias=True)
    payload["videoPath"] = "https://example.invalid/video.mp4"

    with pytest.raises(ValidationError):
        CandidateRuntimeRequest.model_validate(payload)


def test_runtime_rejects_reversed_search_window(tmp_path: Path) -> None:
    payload = _request(tmp_path).model_dump(by_alias=True)
    payload["searchFromMs"] = 5_000
    payload["searchToMs"] = 5_000

    with pytest.raises(ValidationError, match="searchFromMs"):
        CandidateRuntimeRequest.model_validate(payload)


def test_runtime_rejects_candidate_outside_requested_window(tmp_path: Path) -> None:
    request = _request(tmp_path).model_copy(update={"search_from_ms": 2_000})

    with pytest.raises(ValueError, match="outside the requested search window"):
        run_runtime(request.model_dump_json(by_alias=True), FixtureEngine())
