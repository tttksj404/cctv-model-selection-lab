package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobResultResponse;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.util.Map;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisJobResultService {

    private static final String RUNNING = "RUNNING";
    private static final String SUCCEEDED = "SUCCEEDED";

    private final AnalysisJobMapper analysisJobMapper;
    private final CandidateEventCommandService candidateEventCommandService;
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final AuditService auditService;

    public RecordingAnalysisJobResultService(
            AnalysisJobMapper analysisJobMapper,
            CandidateEventCommandService candidateEventCommandService,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            AuditService auditService) {
        this.analysisJobMapper = analysisJobMapper;
        this.candidateEventCommandService = candidateEventCommandService;
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.auditService = auditService;
    }

    @Transactional
    public RecordingAnalysisJobResultResponse complete(
            MediaServerPrincipal principal, Long jobId, CandidateEventCreateRequest request) {
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        if (!RUNNING.equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Only running recording analysis jobs can submit results.");
        }
        if (!job.getCaseId().equals(request.caseId())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "Candidate result case does not match the analysis job.");
        }
        validateCameraOwnership(principal, job, request);

        CandidateEventCreateResponse candidateResult = candidateEventCommandService.create(principal, request);
        if (analysisJobMapper.markSucceeded(job.getCaseId(), jobId) != 1) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Recording analysis job was changed before its result was completed.");
        }

        job.setStatus(SUCCEEDED);
        auditService.recordRequired(
                "RECORDING_ANALYSIS_JOB_SUCCEEDED", null, job.getCaseId(), "ANALYSIS_JOB", jobId,
                Map.of("mediaServerId", principal.mediaServerId(), "candidateEventId", candidateResult.eventId()));
        return new RecordingAnalysisJobResultResponse(
                RecordingAnalysisJobResponse.from(job), candidateResult);
    }

    private void validateCameraOwnership(
            MediaServerPrincipal principal, AnalysisJob job, CandidateEventCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED",
                    "Authentication is required");
        }
        Recording recording = recordingMapper.findById(job.getRecordingId());
        Camera camera = cameraMapper.findByCameraCode(request.cameraCode()).orElseThrow(() ->
                new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), principal.mediaServerId())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED",
                    "Camera does not belong to the authenticated media server");
        }
        if (recording == null || !Objects.equals(recording.getCameraId(), camera.id())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "Candidate result camera does not match the recording analysis job.");
        }
    }
}
