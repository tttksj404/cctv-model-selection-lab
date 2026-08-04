from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

from qwen_backend.candidate_runtime import CandidateRuntimeResponse, RuntimeCandidate
from qwen_backend.central_client import CentralWorkerError
from qwen_backend.worker_protocol import (
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisTarget,
)
from qwen_backend.worker_settings import NotebookWorkerSettings


class EvidenceUploadClient(Protocol):
    """Central API operations required for evidence upload."""

    async def create_evidence_upload_urls(
        self,
        job_id: int,
        claim_token: str,
        candidates: Sequence[RuntimeCandidate],
    ) -> dict[str, RecordingAnalysisEvidenceUpload]: ...

    async def upload_image(
        self,
        url: str,
        source_path: Path,
        *,
        content_type: str,
        max_bytes: int,
    ) -> None: ...


class RecordingDownloadClient(Protocol):
    """Central API and signed-storage operations required for source recording download."""

    async def download(self, url: str, destination: Path, *, max_bytes: int) -> Path: ...

    async def fetch_target(self, job_id: int, claim_token: str) -> RecordingAnalysisTarget: ...


class RecordingEvidenceTransfer:
    """Moves signed recording and evidence files without exposing storage credentials."""

    def __init__(self, settings: NotebookWorkerSettings) -> None:
        self._settings = settings

    async def upload_candidate_evidence(
        self,
        client: EvidenceUploadClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
        runtime_response: CandidateRuntimeResponse,
    ) -> dict[str, RecordingAnalysisEvidenceUpload]:
        if not runtime_response.candidates:
            return {}
        uploads = await client.create_evidence_upload_urls(
            target.job_id,
            lease_token,
            runtime_response.candidates,
        )
        expected_track_ids = {candidate.candidate_key for candidate in runtime_response.candidates}
        if set(uploads) != expected_track_ids:
            raise CentralWorkerError("central evidence response did not match runtime candidates")
        for candidate in runtime_response.candidates:
            upload = uploads[candidate.candidate_key]
            await client.upload_image(
                upload.frame.upload_url,
                candidate.frame_path,
                content_type=upload.frame.content_type,
                max_bytes=self._settings.max_evidence_upload_bytes,
            )
            await client.upload_image(
                upload.crop.upload_url,
                candidate.crop_path,
                content_type=upload.crop.content_type,
                max_bytes=self._settings.max_evidence_upload_bytes,
            )
        return uploads

    async def download_target_recording(
        self,
        client: RecordingDownloadClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
    ) -> tuple[RecordingAnalysisTarget, Path]:
        """Refresh exactly once when the signed URL expires for the same claimed recording."""

        destination = self._settings.cache_dir / f"job-{target.job_id}-attempt-{target.attempt}.mp4"
        try:
            return target, await client.download(
                target.recording_download_url,
                destination,
                max_bytes=self._settings.max_download_bytes,
            )
        except CentralWorkerError as exception:
            if exception.status_code not in {401, 403}:
                raise
            refreshed_target = await client.fetch_target(target.job_id, lease_token)
            if (
                refreshed_target.job_id != target.job_id
                or refreshed_target.attempt != target.attempt
                or refreshed_target.case_id != target.case_id
                or refreshed_target.recording_id != target.recording_id
            ):
                raise CentralWorkerError(
                    "refreshed target no longer matches the claimed recording job"
                ) from exception
            return refreshed_target, await client.download(
                refreshed_target.recording_download_url,
                destination,
                max_bytes=self._settings.max_download_bytes,
            )
