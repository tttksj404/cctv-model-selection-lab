from __future__ import annotations

import logging
import time
from collections.abc import Callable

import anyio
from anyio.to_thread import run_sync

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
)
from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.worker_lease import (
    LeaseHeartbeatContext,
    LeaseLostError,
    maintain_lease,
    raise_if_lease_lost,
)
from qwen_backend.worker_protocol import (
    RecordingAnalysisClaim,
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisResult,
    RecordingAnalysisTarget,
    failure_result_id,
    result_from_runtime,
)
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_transfer import RecordingEvidenceTransfer

logger = logging.getLogger(__name__)

RuntimeRunner = Callable[[CandidateRuntimeRequest], CandidateRuntimeResponse]
ProcessFailure = (
    CentralWorkerError | FileNotFoundError | ImportError | OSError | RuntimeError | ValueError
)


class RecordingJobExecutor:
    """Runs one claimed recording-analysis job through local inference and central callbacks."""

    def __init__(self, settings: NotebookWorkerSettings, runtime_runner: RuntimeRunner) -> None:
        self._settings = settings
        self._runtime_runner = runtime_runner
        self._transfer = RecordingEvidenceTransfer(settings)

    async def process_claim(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
    ) -> bool:
        """Run one claimed recording job and confirm one terminal server callback."""

        if claim.disposition != "CLAIMED":
            raise ValueError("process_claim requires a claim owned by this worker")
        lease_token = claim.lease_token
        if lease_token is None:
            raise ValueError("claimed central job omitted leaseToken")
        try:
            target = await client.fetch_target(claim.job_id, lease_token)
            if target.attempt != claim.attempt:
                raise CentralWorkerError("central target attempt does not match claimed attempt")
            result = await self._process_target(client, target, lease_token)
        except LeaseLostError:
            logger.error(
                "worker lease was lost; terminal callback was not sent job_id=%d", claim.job_id
            )
            return False
        except (
            CentralWorkerError,
            FileNotFoundError,
            ImportError,
            OSError,
            RuntimeError,
            ValueError,
        ) as exception:
            if isinstance(exception, CentralWorkerError) and exception.is_lease_conflict:
                logger.warning(
                    "worker lease conflict before failure callback job_id=%d", claim.job_id
                )
                return False
            return await self._report_failure(client, claim, lease_token, exception)

        try:
            await client.complete(claim.job_id, lease_token, result)
        except CentralWorkerError as exception:
            if exception.is_lease_conflict:
                logger.warning("worker lease conflict on completion job_id=%d", claim.job_id)
                return False
            logger.exception("central completion was not confirmed job_id=%d", claim.job_id)
            raise
        logger.info(
            "AI Worker job completed job_id=%d candidates=%d",
            claim.job_id,
            len(result.candidates),
        )
        return True

    async def _report_failure(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
        lease_token: str,
        exception: ProcessFailure,
    ) -> bool:
        logger.exception("AI Worker job failed job_id=%d", claim.job_id)
        try:
            await client.fail(
                claim.job_id,
                lease_token,
                result_id=failure_result_id(
                    worker_id=self._settings.worker_id,
                    job_id=claim.job_id,
                    attempt=claim.attempt,
                ),
                error_code=type(exception).__name__,
                error_message=" ".join(str(exception).split()) or type(exception).__name__,
            )
        except CentralWorkerError as callback_error:
            if callback_error.is_lease_conflict:
                logger.warning(
                    "worker lease conflict while reporting failure job_id=%d", claim.job_id
                )
                return False
            logger.exception("central failure was not confirmed job_id=%d", claim.job_id)
            raise
        return True

    async def _process_target(
        self,
        client: CentralWorkerClient,
        target: RecordingAnalysisTarget,
        lease_token: str,
    ) -> RecordingAnalysisResult:
        self._settings.cache_dir.mkdir(parents=True, exist_ok=True)
        job_output_dir = self._settings.output_dir / f"job-{target.job_id}-attempt-{target.attempt}"
        job_output_dir.mkdir(parents=True, exist_ok=True)
        stop_heartbeat = anyio.Event()
        lease_lost = anyio.Event()
        fatal_heartbeat_errors: list[CentralWorkerError] = []
        runtime_response: CandidateRuntimeResponse | None = None
        evidence_by_track_id: dict[str, RecordingAnalysisEvidenceUpload] = {}
        started = time.perf_counter()
        heartbeat_context = LeaseHeartbeatContext(
            client=client,
            job_id=target.job_id,
            lease_token=lease_token,
            interval_seconds=self._settings.heartbeat_interval_seconds,
            stop=stop_heartbeat,
            lease_lost=lease_lost,
            fatal_errors=fatal_heartbeat_errors,
        )
        async with anyio.create_task_group() as task_group:
            task_group.start_soon(
                maintain_lease,
                heartbeat_context,
            )
            try:
                target, video_path = await self._transfer.download_target_recording(
                    client,
                    target,
                    lease_token,
                )
                raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
                request = CandidateRuntimeRequest(
                    model_key=self._settings.model_key,
                    job_id=target.job_id,
                    case_id=target.case_id,
                    search_condition_id=target.search_condition_id,
                    recording_id=target.recording_id,
                    camera_id=target.camera_id,
                    camera_name=target.camera_name,
                    camera_address=target.camera_code,
                    video_path=video_path,
                    reference_path=None,
                    output_dir=job_output_dir,
                    prompt=target.prompt,
                    exclusion_prompt=target.exclusion_prompt,
                    similarity_threshold=None,
                    search_from_ms=target.search_from_ms,
                    search_to_ms=target.search_to_ms,
                )
                runtime_response = await run_sync(
                    self._runtime_runner,
                    request,
                    abandon_on_cancel=False,
                )
                raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
                evidence_by_track_id = await self._transfer.upload_candidate_evidence(
                    client,
                    target,
                    lease_token,
                    runtime_response,
                )
                raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
            finally:
                stop_heartbeat.set()
        raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
        if runtime_response is None:
            raise RuntimeError("local inference did not return a response")
        elapsed_ms = round((time.perf_counter() - started) * 1_000)
        logger.info("local inference finished job_id=%d elapsed_ms=%d", target.job_id, elapsed_ms)
        return result_from_runtime(
            runtime_response,
            target,
            worker_id=self._settings.worker_id,
            evidence_by_track_id=evidence_by_track_id,
        )
