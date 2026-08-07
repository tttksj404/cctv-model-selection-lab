from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import anyio
from anyio.to_thread import run_sync

from qwen_backend.candidate_runtime import (
    CandidateRuntimeRequest,
    CandidateRuntimeResponse,
    RuntimeCandidate,
)
from qwen_backend.central_client import CentralWorkerClient, CentralWorkerError
from qwen_backend.recording_cache import RecordingCache, RecordingCacheTarget
from qwen_backend.worker_lease import (
    LeaseHeartbeatContext,
    LeaseLostError,
    maintain_lease,
    raise_if_lease_lost,
)
from qwen_backend.worker_protocol import (
    DeviceAiCompleteCandidate,
    DeviceAiCompleteRequest,
    DeviceAiFailureRequest,
    DeviceAiSearchJob,
    DeviceBoundingBox,
    DeviceCandidateEvent,
    DeviceDetection,
    RabbitWorkerJobEvent,
    RecordingAnalysisClaim,
    RecordingAnalysisEvidenceUpload,
    RecordingAnalysisResult,
    RecordingAnalysisTarget,
    failure_result_id,
    result_from_runtime,
)
from qwen_backend.worker_settings import NotebookWorkerSettings
from qwen_backend.worker_status import NullWorkerStatus, WorkerStage, WorkerStatusSink
from qwen_backend.worker_transfer import RecordingEvidenceTransfer

logger = logging.getLogger(__name__)

RuntimeRunner = Callable[[CandidateRuntimeRequest], CandidateRuntimeResponse]
ProcessFailure = (
    CentralWorkerError | FileNotFoundError | ImportError | OSError | RuntimeError | ValueError
)


def _failure_error_code(exception: ProcessFailure) -> str:
    if isinstance(exception, CentralWorkerError) and exception.code is not None:
        return exception.code
    return type(exception).__name__


class RecordingJobExecutor:
    """Runs one claimed recording-analysis job through local inference and central callbacks."""

    def __init__(
        self,
        settings: NotebookWorkerSettings,
        runtime_runner: RuntimeRunner,
        *,
        status: WorkerStatusSink | None = None,
    ) -> None:
        self._settings = settings
        self._runtime_runner = runtime_runner
        self._status = status or NullWorkerStatus()
        self._transfer = RecordingEvidenceTransfer(settings)
        self._recording_cache = RecordingCache(settings.cache_dir)

    async def _download_recording_with_cache(
        self,
        client: CentralWorkerClient,
        recording_object_key: str,
        *,
        download_url: str | None = None,
    ) -> Path:
        """Reuse a complete object-key cache for every worker API path."""

        target = RecordingCacheTarget(recording_object_key=recording_object_key)
        cached = self._recording_cache.find(target, "full")
        if cached is not None:
            logger.info(
                "recording cache hit job_source=%s mode=full file=%s",
                recording_object_key,
                cached.name,
            )
            return cached
        destination = self._recording_cache.paths(target, "full").video_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        logger.info("recording network download started mode=full")
        if download_url is not None:
            path = await client.download(
                download_url,
                destination,
                max_bytes=self._settings.max_download_bytes,
            )
        else:
            path = await client.download_object(
                recording_object_key,
                destination,
                max_bytes=self._settings.max_download_bytes,
            )
        self._recording_cache.store(target, "full", path)
        logger.info("recording network download completed mode=full")
        return path

    async def process_claim(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
    ) -> bool:
        """Run one claimed recording job and confirm one terminal server callback."""

        if claim.disposition != "CLAIMED":
            raise ValueError("process_claim requires a claim owned by this worker")
        lease_token = claim.lease_token
        try:
            self._status.update(
                WorkerStage.FETCHING_TARGET,
                "백엔드에서 작업 정보를 확인하는 중",
                job_id=claim.job_id,
            )
            target = await client.fetch_target(claim.job_id, lease_token)
            if target.attempt != claim.attempt:
                raise CentralWorkerError("central target attempt does not match claimed attempt")
            result = await self._process_target(client, target, lease_token)
        except LeaseLostError:
            logger.error(
                "worker lease was lost; terminal callback was not sent job_id=%d", claim.job_id
            )
            self._status.update(
                WorkerStage.FAILED,
                "작업 lease가 만료되어 결과를 확정하지 못함",
                job_id=claim.job_id,
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
            self._status.update(
                WorkerStage.COMPLETING,
                "중앙 서버에 추론 결과를 저장하는 중",
                job_id=claim.job_id,
                candidate_count=len(result.candidates),
            )
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
        self._status.update(
            WorkerStage.SUCCEEDED,
            "추론 완료",
            job_id=claim.job_id,
            progress=100,
            candidate_count=len(result.candidates),
        )
        return True

    async def process_device_event(
        self,
        client: CentralWorkerClient,
        event: RabbitWorkerJobEvent,
    ) -> bool:
        """Run the pre-Worker-API enriched event through the Device Key path."""

        if not client.uses_device_key:
            raise CentralWorkerError("legacy Device event requires Device Key authentication")
        target = _legacy_target(event)
        self._status.update(
            WorkerStage.FETCHING_TARGET,
            "레거시 작업 정보를 확인하는 중",
            job_id=target.job_id,
        )
        self._settings.cache_dir.mkdir(parents=True, exist_ok=True)
        job_output_dir = self._settings.output_dir / f"job-{target.job_id}-attempt-{target.attempt}"
        job_output_dir.mkdir(parents=True, exist_ok=True)
        self._status.update(
            WorkerStage.DOWNLOADING,
            "녹화본을 노트북으로 다운로드하는 중",
            job_id=target.job_id,
        )
        video_path = await self._download_recording_with_cache(
            client,
            target.recording_object_key,
            download_url=event.recording_download_url,
        )
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
            similarity_threshold=target.similarity_threshold,
            search_from_ms=target.search_from_ms,
            search_to_ms=target.search_to_ms,
        )
        self._status.update(
            WorkerStage.INFERENCING,
            "로컬 모델 추론 진행 중",
            job_id=target.job_id,
        )
        runtime_response = await run_sync(
            self._runtime_runner,
            request,
            abandon_on_cancel=False,
        )
        if not runtime_response.candidates:
            raise DeviceEventContractError(
                "legacy Device result endpoint cannot complete a recording job with no candidates"
            )

        # The legacy result endpoint accepts one frame plus its detections.  To
        # avoid marking the job succeeded multiple times, submit the highest
        # scoring frame group as one atomic candidate event.
        selected = _select_device_frame_group(runtime_response.candidates)
        frame_content_type = _image_content_type(selected[0].frame_path)
        frame_key = _analysis_object_key(
            target.job_id,
            target.attempt,
            "frames",
            "frame",
            frame_content_type,
        )
        await client.upload_object(
            frame_key,
            selected[0].frame_path,
            content_type=frame_content_type,
            max_bytes=self._settings.max_evidence_upload_bytes,
        )
        detections: list[DeviceDetection] = []
        for candidate in selected:
            crop_content_type = _image_content_type(candidate.crop_path)
            crop_key = _analysis_object_key(
                target.job_id,
                target.attempt,
                "crops",
                candidate.candidate_key,
                crop_content_type,
            )
            await client.upload_object(
                crop_key,
                candidate.crop_path,
                content_type=crop_content_type,
                max_bytes=self._settings.max_evidence_upload_bytes,
            )
            detections.append(
                DeviceDetection(
                    track_id=candidate.candidate_key,
                    similarity=candidate.similarity,
                    crop_object_key=crop_key,
                    bounding_box=DeviceBoundingBox(
                        x=candidate.bounding_box.x,
                        y=candidate.bounding_box.y,
                        width=candidate.bounding_box.width,
                        height=candidate.bounding_box.height,
                    ),
                )
            )
        result = DeviceCandidateEvent(
            case_id=target.case_id,
            camera_code=target.camera_code,
            event_id=f"analysis-{target.job_id}-attempt-{target.attempt}",
            detected_at=target.recording_start,
            frame_object_key=frame_key,
            detections=tuple(detections),
        )
        await client.complete_device_result(target.job_id, result)
        logger.info(
            "legacy Device Key AI Worker job completed job_id=%d candidates=%d",
            target.job_id,
            len(selected),
        )
        self._status.update(
            WorkerStage.SUCCEEDED,
            "추론 완료",
            job_id=target.job_id,
            progress=100,
            candidate_count=len(selected),
        )
        return True

    async def process_device_claim(
        self,
        client: CentralWorkerClient,
        job: DeviceAiSearchJob,
    ) -> bool:
        """Run one current `/device/ai/jobs` claim end to end.

        The current backend returns object keys with the claim, so the worker
        downloads and uploads through its private S3/MinIO adapter and sends
        only result object keys back to the central API.
        """

        if not client.uses_current_device_api:
            raise CentralWorkerError("current Device API claim requires Device Key authentication")
        self._settings.cache_dir.mkdir(parents=True, exist_ok=True)
        job_output_dir = self._settings.output_dir / f"job-{job.job_id}-attempt-{job.attempt}"
        job_output_dir.mkdir(parents=True, exist_ok=True)
        stop_heartbeat = anyio.Event()
        lease_lost = anyio.Event()
        fatal_heartbeat_errors: list[CentralWorkerError] = []
        heartbeat_context = LeaseHeartbeatContext(
            client=client,
            job_id=job.job_id,
            lease_token=job.lease_token,
            interval_seconds=self._settings.heartbeat_interval_seconds,
            stop=stop_heartbeat,
            lease_lost=lease_lost,
            fatal_errors=fatal_heartbeat_errors,
        )
        try:
            async with anyio.create_task_group() as task_group:
                task_group.start_soon(maintain_lease, heartbeat_context)
                try:
                    self._status.update(
                        WorkerStage.DOWNLOADING,
                        "녹화본과 신고자 기준 사진을 로컬로 내려받는 중",
                        job_id=job.job_id,
                    )
                    video_path = await self._download_recording_with_cache(
                        client,
                        job.recording_object_key,
                    )
                    reference_path: Path | None = None
                    if job.reference_photo_object_key:
                        reference_path = await client.download_object(
                            job.reference_photo_object_key,
                            self._settings.cache_dir
                            / f"job-{job.job_id}-attempt-{job.attempt}-reference.jpg",
                            max_bytes=self._settings.max_evidence_upload_bytes,
                        )
                    duration_ms = max(
                        1,
                        round((job.recording_end - job.recording_start).total_seconds() * 1_000),
                    )
                    request = CandidateRuntimeRequest(
                        model_key=self._settings.model_key,
                        job_id=job.job_id,
                        case_id=job.case_id,
                        search_condition_id=job.search_condition_id,
                        recording_id=job.recording_id,
                        camera_id=job.camera_id,
                        camera_name=job.camera_name,
                        camera_address=job.camera_address or job.camera_name,
                        video_path=video_path,
                        reference_path=reference_path,
                        output_dir=job_output_dir,
                        prompt=job.prompt,
                        exclusion_prompt=job.exclusion_prompt,
                        similarity_threshold=job.similarity_threshold,
                        search_from_ms=0,
                        search_to_ms=duration_ms,
                    )
                    self._status.update(
                        WorkerStage.INFERENCING,
                        "로컬 GPU 모델 추론을 진행하는 중",
                        job_id=job.job_id,
                    )
                    runtime_response = await run_sync(
                        self._runtime_runner,
                        request,
                        abandon_on_cancel=False,
                    )
                    raise_if_lease_lost(lease_lost, job.job_id, fatal_heartbeat_errors)
                    self._status.update(
                        WorkerStage.UPLOADING,
                        "후보 프레임과 crop을 MinIO/S3에 업로드하는 중",
                        job_id=job.job_id,
                        candidate_count=len(runtime_response.candidates),
                    )
                    candidates: list[DeviceAiCompleteCandidate] = []
                    for candidate in runtime_response.candidates:
                        frame_content_type = _image_content_type(candidate.frame_path)
                        crop_content_type = _image_content_type(candidate.crop_path)
                        frame_key = _current_result_object_key(
                            job.job_id,
                            candidate.candidate_key,
                            "frames",
                            frame_content_type,
                        )
                        crop_key = _current_result_object_key(
                            job.job_id,
                            candidate.candidate_key,
                            "crops",
                            crop_content_type,
                        )
                        await client.upload_object(
                            frame_key,
                            candidate.frame_path,
                            content_type=frame_content_type,
                            max_bytes=self._settings.max_evidence_upload_bytes,
                        )
                        await client.upload_object(
                            crop_key,
                            candidate.crop_path,
                            content_type=crop_content_type,
                            max_bytes=self._settings.max_evidence_upload_bytes,
                        )
                        candidates.append(
                            DeviceAiCompleteCandidate(
                                candidate_key=candidate.candidate_key,
                                frame_offset_ms=candidate.frame_offset_ms,
                                similarity=candidate.similarity,
                                crop_object_key=crop_key,
                                clip_object_key=frame_key,
                                bounding_box=DeviceBoundingBox(
                                    x=candidate.bounding_box.x,
                                    y=candidate.bounding_box.y,
                                    width=candidate.bounding_box.width,
                                    height=candidate.bounding_box.height,
                                ),
                                attribute_summary=candidate.attribute_summary,
                            )
                        )
                    raise_if_lease_lost(lease_lost, job.job_id, fatal_heartbeat_errors)
                    await client.complete_device_job(
                        job.job_id,
                        DeviceAiCompleteRequest(
                            lease_token=job.lease_token,
                            model_key=self._settings.model_key,
                            candidates=tuple(candidates),
                        ),
                    )
                finally:
                    stop_heartbeat.set()
            self._status.update(
                WorkerStage.SUCCEEDED,
                "추론 및 중앙 서버 결과 반영 완료",
                job_id=job.job_id,
                progress=100,
            )
            return True
        except LeaseLostError:
            logger.error("current Device API lease was lost job_id=%d", job.job_id)
            self._status.update(
                WorkerStage.FAILED,
                "작업 lease가 만료되어 결과를 확정하지 못함",
                job_id=job.job_id,
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
                return False
            return await self._report_device_failure(client, job, exception)

    async def _report_device_failure(
        self,
        client: CentralWorkerClient,
        job: DeviceAiSearchJob,
        exception: ProcessFailure,
    ) -> bool:
        logger.exception("current Device API AI Worker job failed job_id=%d", job.job_id)
        self._status.update(
            WorkerStage.FAILED,
            f"추론 실패: {type(exception).__name__}",
            job_id=job.job_id,
        )
        await client.fail_device_job(
            job.job_id,
            DeviceAiFailureRequest(
                lease_token=job.lease_token,
                error_code=type(exception).__name__,
                error_message=" ".join(str(exception).split()) or type(exception).__name__,
                retryable=not isinstance(exception, ValueError),
            ),
        )
        return True

    async def _report_failure(
        self,
        client: CentralWorkerClient,
        claim: RecordingAnalysisClaim,
        lease_token: str | None,
        exception: ProcessFailure,
    ) -> bool:
        logger.exception("AI Worker job failed job_id=%d", claim.job_id)
        self._status.update(
            WorkerStage.FAILED,
            f"추론 실패: {type(exception).__name__}",
            job_id=claim.job_id,
        )
        try:
            await client.fail(
                claim.job_id,
                lease_token,
                result_id=failure_result_id(
                    worker_id=self._settings.worker_id,
                    job_id=claim.job_id,
                    attempt=claim.attempt,
                ),
                error_code=_failure_error_code(exception),
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
        lease_token: str | None,
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
        async with anyio.create_task_group() as task_group:
            if lease_token is not None:
                heartbeat_context = LeaseHeartbeatContext(
                    client=client,
                    job_id=target.job_id,
                    lease_token=lease_token,
                    interval_seconds=self._settings.heartbeat_interval_seconds,
                    stop=stop_heartbeat,
                    lease_lost=lease_lost,
                    fatal_errors=fatal_heartbeat_errors,
                )
                task_group.start_soon(
                    maintain_lease,
                    heartbeat_context,
                )
            try:
                self._status.update(
                    WorkerStage.DOWNLOADING,
                    "녹화본을 노트북으로 다운로드하는 중",
                    job_id=target.job_id,
                )
                download_started = time.perf_counter()
                target, video_path = await self._transfer.download_target_recording(
                    client,
                    target,
                    lease_token,
                )
                logger.info(
                    "recording source resolved job_id=%d elapsed_ms=%d",
                    target.job_id,
                    round((time.perf_counter() - download_started) * 1_000),
                )
                if lease_token is not None:
                    raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
                reference_path: Path | None = None
                if target.reference_photo_object_key:
                    reference_destination = (
                        self._settings.cache_dir
                        / f"job-{target.job_id}-attempt-{target.attempt}-reference.jpg"
                    )
                    if target.reference_photo_download_url:
                        reference_path = await client.download(
                            target.reference_photo_download_url,
                            reference_destination,
                            max_bytes=self._settings.max_evidence_upload_bytes,
                        )
                    else:
                        reference_path = await client.download_object(
                            target.reference_photo_object_key,
                            reference_destination,
                            max_bytes=self._settings.max_evidence_upload_bytes,
                        )
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
                    reference_path=reference_path,
                    output_dir=job_output_dir,
                    prompt=target.prompt,
                    exclusion_prompt=target.exclusion_prompt,
                    similarity_threshold=target.similarity_threshold,
                    search_from_ms=target.search_from_ms,
                    search_to_ms=target.search_to_ms,
                )
                self._status.update(
                    WorkerStage.INFERENCING,
                    "로컬 모델 추론 진행 중",
                    job_id=target.job_id,
                )
                inference_started = time.perf_counter()
                runtime_response = await run_sync(
                    self._runtime_runner,
                    request,
                    abandon_on_cancel=False,
                )
                logger.info(
                    "local inference finished job_id=%d candidates=%d elapsed_ms=%d",
                    target.job_id,
                    len(runtime_response.candidates),
                    round((time.perf_counter() - inference_started) * 1_000),
                )
                if lease_token is not None:
                    raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
                self._status.update(
                    WorkerStage.UPLOADING,
                    "후보 프레임과 크롭을 업로드하는 중",
                    job_id=target.job_id,
                    candidate_count=len(runtime_response.candidates),
                )
                evidence_upload_started = time.perf_counter()
                evidence_by_track_id = await self._transfer.upload_candidate_evidence(
                    client,
                    target,
                    lease_token,
                    runtime_response,
                )
                logger.info(
                    "candidate evidence upload stage finished job_id=%d candidates=%d "
                    "elapsed_ms=%d",
                    target.job_id,
                    len(runtime_response.candidates),
                    round((time.perf_counter() - evidence_upload_started) * 1_000),
                )
                if lease_token is not None:
                    raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
            finally:
                stop_heartbeat.set()
        if lease_token is not None:
            raise_if_lease_lost(lease_lost, target.job_id, fatal_heartbeat_errors)
        if runtime_response is None:
            raise RuntimeError("local inference did not return a response")
        result = result_from_runtime(
            runtime_response,
            target,
            worker_id=self._settings.worker_id,
            evidence_by_track_id=evidence_by_track_id,
        )
        logger.info(
            "recording target prepared for central result job_id=%d candidates=%d elapsed_ms=%d",
            target.job_id,
            len(result.candidates),
            round((time.perf_counter() - started) * 1_000),
        )
        return result


class DeviceEventContractError(ValueError):
    """The legacy enriched Rabbit event cannot satisfy the Device API."""


@dataclass(frozen=True, slots=True)
class _LegacyTarget:
    job_id: int
    attempt: int
    case_id: int
    search_condition_id: int
    recording_id: int
    camera_id: int
    camera_code: str
    camera_name: str
    recording_object_key: str
    prompt: str
    exclusion_prompt: str | None
    similarity_threshold: float | None
    recording_start: datetime
    search_from_ms: int
    search_to_ms: int | None

    @classmethod
    def from_event(cls, event: RabbitWorkerJobEvent) -> _LegacyTarget:
        missing = [
            name
            for name, value in (
                ("caseId", event.case_id),
                ("recordingId", event.recording_id),
                ("cameraId", event.camera_id),
                ("cameraCode", event.camera_code),
                ("cameraName", event.camera_name),
                ("recordingObjectKey", event.recording_object_key),
                ("prompt", event.prompt),
            )
            if value is None
        ]
        if missing:
            raise DeviceEventContractError(
                "legacy Rabbit event is missing required fields: " + ", ".join(missing)
            )
        assert event.case_id is not None
        assert event.recording_id is not None
        assert event.camera_id is not None
        assert event.camera_code is not None
        assert event.camera_name is not None
        assert event.recording_object_key is not None
        assert event.prompt is not None
        return cls(
            job_id=event.job_id,
            attempt=event.attempt or 1,
            case_id=event.case_id,
            search_condition_id=event.search_condition_id or event.case_id,
            recording_id=event.recording_id,
            camera_id=event.camera_id,
            camera_code=event.camera_code,
            camera_name=event.camera_name,
            recording_object_key=event.recording_object_key,
            prompt=event.prompt,
            exclusion_prompt=event.exclusion_prompt,
            similarity_threshold=event.similarity_threshold,
            recording_start=event.recording_start or event.search_start or event.occurred_at,
            search_from_ms=event.search_from_ms or 0,
            search_to_ms=event.search_to_ms or _duration_ms(event.search_start, event.search_end),
        )


def _legacy_target(event: RabbitWorkerJobEvent) -> _LegacyTarget:
    return _LegacyTarget.from_event(event)


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    if start is None or end is None or end <= start:
        return None
    return max(1, round((end - start).total_seconds() * 1_000))


def _select_device_frame_group(
    candidates: tuple[RuntimeCandidate, ...],
) -> tuple[RuntimeCandidate, ...]:
    best = max(candidates, key=lambda candidate: candidate.similarity)
    selected = tuple(
        candidate for candidate in candidates if candidate.frame_path == best.frame_path
    )
    return tuple(
        sorted(
            selected,
            key=lambda candidate: (-candidate.similarity, candidate.candidate_key),
        )
    )


def _image_content_type(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def _analysis_object_key(
    job_id: int,
    attempt: int,
    directory: str,
    stem: str,
    content_type: str,
) -> str:
    extension = "png" if content_type == "image/png" else "jpg"
    safe_stem = "".join(char if char.isalnum() or char in "-_." else "_" for char in stem)
    safe_stem = safe_stem[:100] or "candidate"
    return f"analysis/analysis-{job_id}/attempt-{attempt}/{directory}/{safe_stem}.{extension}"


def _current_result_object_key(
    job_id: int,
    candidate_key: str,
    directory: str,
    content_type: str,
) -> str:
    """Build a backend-accepted result key under ``ai-results/{jobId}/``."""

    extension = "png" if content_type == "image/png" else "jpg"
    safe_key = "".join(char if char.isalnum() or char in "-_." else "_" for char in candidate_key)
    safe_key = safe_key[:100] or "candidate"
    return f"ai-results/{job_id}/{directory}/{safe_key}.{extension}"
