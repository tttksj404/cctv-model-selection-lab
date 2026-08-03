package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.missingcase.service.CandidateEventStorageValidator;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobResultResponse;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class RecordingAnalysisJobResultService {

    private static final String RUNNING = "RUNNING";
    private static final String SUCCEEDED = "SUCCEEDED";

    private final AnalysisJobMapper analysisJobMapper;
    private final CandidateEventCommandService candidateEventCommandService;
    private final RecordingMapper recordingMapper;
    private final AuditService auditService;
    private final CandidateEventStorageValidator storageValidator;
    private final TransactionTemplate transactionTemplate;

    public RecordingAnalysisJobResultService(
            AnalysisJobMapper analysisJobMapper,
            CandidateEventCommandService candidateEventCommandService,
            RecordingMapper recordingMapper,
            AuditService auditService,
            CandidateEventStorageValidator storageValidator,
            TransactionTemplate transactionTemplate) {
        this.analysisJobMapper = analysisJobMapper;
        this.candidateEventCommandService = candidateEventCommandService;
        this.recordingMapper = recordingMapper;
        this.auditService = auditService;
        this.storageValidator = storageValidator;
        this.transactionTemplate = transactionTemplate;
    }

    public RecordingAnalysisJobResultResponse complete(
            MediaServerPrincipal principal, Long jobId, CandidateEventCreateRequest request) {
        validateJob(principal, jobId, request);
        storageValidator.verify(request);
        return transactionTemplate.execute(status -> completeInTransaction(principal, jobId, request));
    }

    private RecordingAnalysisJobResultResponse completeInTransaction(
            MediaServerPrincipal principal, Long jobId, CandidateEventCreateRequest request) {
        ValidatedJob validated = validateJob(principal, jobId, request);
        AnalysisJob job = validated.job();
        Long recordingCameraId = validated.cameraId();

        CandidateEventCreateResponse candidateResult = candidateEventCommandService.create(
                principal, request, recordingCameraId);
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

    private ValidatedJob validateJob(
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
        Long recordingCameraId = validateRecordingTarget(principal, job);
        return new ValidatedJob(job, recordingCameraId);
    }

    private Long validateRecordingTarget(MediaServerPrincipal principal, AnalysisJob job) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED",
                    "Authentication is required");
        }
        Recording recording = recordingMapper.findById(job.getRecordingId());
        if (recording == null || recording.getCameraId() == null) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "Candidate result camera does not match the recording analysis job.");
        }
        return recording.getCameraId();
    }

    private record ValidatedJob(AnalysisJob job, Long cameraId) {
    }
}
