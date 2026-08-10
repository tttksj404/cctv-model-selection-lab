from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import anyio

from qwen_backend.candidate_runtime import (
    CandidateRuntimeResponse,
    RuntimeBoundingBox,
    RuntimeCandidate,
)
from qwen_backend.worker_protocol import RecordingAnalysisEvidenceUpload
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_transfer import RecordingEvidenceTransfer


class _UploadClient:
    def __init__(self) -> None:
        self.active_uploads = 0
        self.max_active_uploads = 0
        self.calls: list[str] = []

    async def create_evidence_upload_urls(
        self,
        job_id: int,
        claim_token: str | None,
        candidates: tuple[RuntimeCandidate, ...],
    ) -> dict[str, RecordingAnalysisEvidenceUpload]:
        assert job_id == 71
        assert claim_token == "lease-1"
        return {
            candidate.candidate_key: RecordingAnalysisEvidenceUpload.model_validate(
                {
                    "trackId": candidate.candidate_key,
                    "frame": {
                        "objectKey": f"analysis/71/frames/{candidate.candidate_key}.jpg",
                        "uploadUrl": f"https://storage.example/frame/{candidate.candidate_key}",
                        "contentType": "image/jpeg",
                    },
                    "crop": {
                        "objectKey": f"analysis/71/crops/{candidate.candidate_key}.jpg",
                        "uploadUrl": f"https://storage.example/crop/{candidate.candidate_key}",
                        "contentType": "image/jpeg",
                    },
                }
            )
            for candidate in candidates
        }

    async def upload_image(
        self,
        url: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None:
        del content_type, max_bytes
        self.active_uploads += 1
        self.max_active_uploads = max(self.max_active_uploads, self.active_uploads)
        self.calls.append(url)
        try:
            await anyio.sleep(0.02)
        finally:
            self.active_uploads -= 1
        assert source_path.exists()


def test_candidate_evidence_uploads_are_bounded_and_concurrent(tmp_path: Path) -> None:
    candidates = tuple(
        RuntimeCandidate(
            candidate_key=f"track-{index}",
            frame_offset_ms=index * 1_000,
            similarity=0.9,
            frame_path=tmp_path / f"frame-{index}.jpg",
            crop_path=tmp_path / f"crop-{index}.jpg",
            bounding_box=RuntimeBoundingBox(x=1, y=2, width=3, height=4),
        )
        for index in range(5)
    )
    for candidate in candidates:
        candidate.frame_path.write_bytes(b"frame")
        candidate.crop_path.write_bytes(b"crop")

    runtime_response = CandidateRuntimeResponse(model_key="fixture", candidates=candidates)
    settings = NotebookWorkerSettings(
        central_api_url="https://central.example",
        api_key="worker-key",
        worker_id="notebook-test",
        evidence_upload_concurrency=2,
    )
    client = _UploadClient()

    async def scenario() -> None:
        uploads = await RecordingEvidenceTransfer(settings).upload_candidate_evidence(
            client,
            SimpleNamespace(job_id=71),
            "lease-1",
            runtime_response,
        )
        assert set(uploads) == {candidate.candidate_key for candidate in candidates}

    anyio.run(scenario)

    assert client.max_active_uploads == 2
    assert len(client.calls) == len(candidates) * 2

