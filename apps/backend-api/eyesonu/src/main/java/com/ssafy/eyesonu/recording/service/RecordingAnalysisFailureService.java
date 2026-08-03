package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisResultMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.HexFormat;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisFailureService {

    private final AnalysisJobMapper jobMapper;
    private final RecordingAnalysisResultMapper resultMapper;
    private final AuditService auditService;

    public RecordingAnalysisFailureService(
            AnalysisJobMapper jobMapper,
            RecordingAnalysisResultMapper resultMapper,
            AuditService auditService) {
        this.jobMapper = jobMapper;
        this.resultMapper = resultMapper;
        this.auditService = auditService;
    }

    @Transactional
    public RecordingAnalysisFailureResponse fail(
            Long jobId, RecordingAnalysisFailureRequest request, String workerId) {
        AnalysisJob job = jobMapper.findRecordingAnalysisByIdForUpdate(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        int attempt = job.getRetryCount() + 1;
        String payloadHash = payloadHash(request);
        RecordingAnalysisResult existing = resultMapper.findByJobIdAndAttempt(jobId, attempt);
        if (existing != null) {
            if (existing.getResultId().equals(request.resultId())
                    && existing.getPayloadHash().equals(payloadHash)
                    && "FAILED".equals(existing.getStatus())) {
                return new RecordingAnalysisFailureResponse(
                        jobId, request.resultId(), job.getStatus(), attempt, true, job.getCompletedAt());
            }
            throw new ApiException(HttpStatus.CONFLICT, "RESULT_ID_CONFLICT",
                    "A different terminal result was already submitted for this attempt.");
        }
        if (!"RUNNING".equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT, "JOB_NOT_RUNNABLE",
                    "Only running recording analysis jobs can report failure.");
        }

        RecordingAnalysisResult result = new RecordingAnalysisResult();
        result.setJobId(jobId);
        result.setAttempt(attempt);
        result.setResultId(request.resultId());
        result.setPayloadHash(payloadHash);
        result.setStatus("FAILED");
        result.setCandidateCount(0);
        result.setErrorCode(request.errorCode());
        result.setErrorMessage(request.errorMessage());
        resultMapper.insert(result);
        String storedError = request.errorMessage() == null || request.errorMessage().isBlank()
                ? request.errorCode() : request.errorCode() + ": " + request.errorMessage();
        if (jobMapper.markFailed(job.getCaseId(), jobId, storedError) != 1) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Recording analysis job changed before failure was recorded.");
        }
        job.setStatus("FAILED");
        job.setCompletedAt(Instant.now());
        auditService.recordRequired(
                "RECORDING_ANALYSIS_JOB_FAILED", null, job.getCaseId(), "ANALYSIS_JOB", jobId,
                Map.of("workerId", workerId, "errorCode", request.errorCode(), "attempt", attempt));
        return new RecordingAnalysisFailureResponse(
                jobId, request.resultId(), job.getStatus(), attempt, false, job.getCompletedAt());
    }

    private String payloadHash(RecordingAnalysisFailureRequest request) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(request.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
