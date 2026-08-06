from __future__ import annotations

import logging
import time
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path
from typing import Protocol

import anyio

from qwen_backend.candidate_runtime import CandidateRuntimeResponse, RuntimeCandidate
from qwen_backend.central_client import CentralWorkerError
from qwen_backend.worker_protocol import (
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisTarget,
)
from qwen_backend.worker_settings import NotebookWorkerSettings

logger = logging.getLogger(__name__)


class EvidenceUploadClient(Protocol):
    """Central API operations required for evidence upload."""

    async def create_evidence_upload_urls(
        self,
        job_id: int,
        claim_token: str | None,
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

    async def download_segment(
        self,
        url: str,
        destination: Path,
        *,
        start_ms: int,
        end_ms: int,
        max_bytes: int,
        ffmpeg_path: str,
        timeout_seconds: float,
    ) -> Path: ...

    async def fetch_target(
        self,
        job_id: int,
        claim_token: str | None,
    ) -> RecordingAnalysisTarget: ...


class RecordingEvidenceTransfer:
    """Moves signed recording and evidence files without exposing storage credentials."""

    def __init__(self, settings: NotebookWorkerSettings) -> None:
        self._settings = settings

    async def upload_candidate_evidence(
        self,
        client: EvidenceUploadClient,
        target: RecordingAnalysisTarget,
        lease_token: str | None,
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
        started = time.perf_counter()
        errors: list[Exception] = []
        limiter = anyio.CapacityLimiter(self._settings.evidence_upload_concurrency)

        async def upload_candidate(candidate: RuntimeCandidate) -> None:
            try:
                async with limiter:
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
            except Exception as error:
                errors.append(error)
                task_group.cancel_scope.cancel()

        async with anyio.create_task_group() as task_group:
            for candidate in runtime_response.candidates:
                task_group.start_soon(upload_candidate, candidate)
        if errors:
            raise errors[0]
        logger.info(
            "candidate evidence upload finished job_id=%d candidates=%d "
            "concurrency=%d elapsed_ms=%d",
            target.job_id,
            len(runtime_response.candidates),
            self._settings.evidence_upload_concurrency,
            round((time.perf_counter() - started) * 1_000),
        )
        return uploads

    async def download_target_recording(
        self,
        client: RecordingDownloadClient,
        target: RecordingAnalysisTarget,
        lease_token: str | None,
    ) -> tuple[RecordingAnalysisTarget, Path]:
        """Refresh exactly once when the signed URL expires for the same claimed recording."""

        destination = self._destination_for(target)
        try:
            return await self._download_once(client, target, destination)
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
            return await self._download_once(client, refreshed_target, destination)

    def _destination_for(self, target: RecordingAnalysisTarget) -> Path:
        suffix = ".window.mp4" if self._settings.download_window_mode == "segment" else ".mp4"
        return self._settings.cache_dir / (
            f"job-{target.job_id}-attempt-{target.attempt}{suffix}"
        )

    async def _download_once(
        self,
        client: RecordingDownloadClient,
        target: RecordingAnalysisTarget,
        destination: Path,
    ) -> tuple[RecordingAnalysisTarget, Path]:
        if target.recording_download_url is None:
            raise CentralWorkerError(
                "RecordingAnalysisWorkerController target omitted recordingDownloadUrl",
                code="WORKER_TARGET_MISSING_DOWNLOAD_URL",
            )
        if self._settings.download_window_mode == "segment":
            path = await client.download_segment(
                target.recording_download_url,
                destination,
                start_ms=target.search_from_ms,
                end_ms=target.search_to_ms,
                max_bytes=self._settings.max_download_bytes,
                ffmpeg_path=self._settings.ffmpeg_path,
                timeout_seconds=self._settings.segment_timeout_seconds,
            )
            return _segment_target(target), path
        return target, await client.download(
            target.recording_download_url,
            destination,
            max_bytes=self._settings.max_download_bytes,
        )


def _segment_target(target: RecordingAnalysisTarget) -> RecordingAnalysisTarget:
    """Translate local segment timestamps back to the original recording timeline."""

    window_duration_ms = target.search_to_ms - target.search_from_ms
    segment_start = target.recording_start + timedelta(milliseconds=target.search_from_ms)
    segment_end = segment_start + timedelta(milliseconds=window_duration_ms)
    return target.model_copy(
        update={
            "recording_start": segment_start,
            "recording_end": segment_end,
            "search_start": segment_start,
            "search_end": segment_end,
            "search_from_ms": 0,
            "search_to_ms": window_duration_ms,
        }
    )
