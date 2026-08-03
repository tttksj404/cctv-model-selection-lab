package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisResultMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.HexFormat;
import java.util.List;
import java.util.Map;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@Service
public class RecordingAnalysisBatchResultService {

    private final AnalysisJobMapper jobMapper;
    private final RecordingAnalysisResultMapper resultMapper;
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final CandidateEventCommandService candidateService;
    private final AuditService auditService;
    private final RecordingAnalysisResultStorageValidator resultStorageValidator;
    private final TransactionTemplate transactionTemplate;

    public RecordingAnalysisBatchResultService(
            AnalysisJobMapper jobMapper,
            RecordingAnalysisResultMapper resultMapper,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            CandidateEventCommandService candidateService,
            AuditService auditService,
            RecordingAnalysisResultStorageValidator resultStorageValidator,
            PlatformTransactionManager transactionManager) {
        this(jobMapper, resultMapper, recordingMapper, cameraMapper, candidateService,
                auditService, resultStorageValidator, new TransactionTemplate(transactionManager));
    }

    RecordingAnalysisBatchResultService(
            AnalysisJobMapper jobMapper,
            RecordingAnalysisResultMapper resultMapper,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            CandidateEventCommandService candidateService,
            AuditService auditService,
            RecordingAnalysisResultStorageValidator resultStorageValidator,
            TransactionTemplate transactionTemplate) {
        this.jobMapper = jobMapper;
        this.resultMapper = resultMapper;
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.candidateService = candidateService;
        this.auditService = auditService;
        this.resultStorageValidator = resultStorageValidator;
        this.transactionTemplate = transactionTemplate;
    }

    public RecordingAnalysisBatchResultResponse complete(
            Long jobId, RecordingAnalysisBatchResultRequest request, String workerId) {
        validateUniqueTracks(request);
        String payloadHash = payloadHash(request);
        // External storage calls must not run while the database row is locked.
        AnalysisJob job = jobMapper.findRecordingAnalysisById(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }

        int attempt = job.getRetryCount() + 1;
        RecordingAnalysisResult existing = resultMapper.findByJobIdAndAttempt(jobId, attempt);
        if (existing != null) {
            if (existing.getResultId().equals(request.resultId())
                    && existing.getPayloadHash().equals(payloadHash)) {
                return new RecordingAnalysisBatchResultResponse(
                        jobId, existing.getResultId(), job.getStatus(), existing.getCandidateCount(),
                        List.of(), true, job.getCompletedAt());
            }
            throw new ApiException(HttpStatus.CONFLICT, "RESULT_ID_CONFLICT",
                    "A different result was already submitted for this job.");
        }
        if (!"RUNNING".equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT, "JOB_NOT_RUNNABLE",
                    "Only running recording analysis jobs can submit results.");
        }
        resultStorageValidator.verify(job, request);

        RecordingAnalysisBatchResultResponse response = transactionTemplate.execute(status ->
                completeInTransaction(jobId, request, workerId, payloadHash));
        if (response == null) {
            throw new IllegalStateException("Recording analysis completion transaction returned no result");
        }
        return response;
    }

    private RecordingAnalysisBatchResultResponse completeInTransaction(
            Long jobId, RecordingAnalysisBatchResultRequest request, String workerId, String payloadHash) {
        AnalysisJob job = jobMapper.findRecordingAnalysisByIdForUpdate(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        int attempt = job.getRetryCount() + 1;
        RecordingAnalysisResult existing = resultMapper.findByJobIdAndAttempt(jobId, attempt);
        if (existing != null) {
            if (existing.getResultId().equals(request.resultId())
                    && existing.getPayloadHash().equals(payloadHash)) {
                return new RecordingAnalysisBatchResultResponse(
                        jobId, existing.getResultId(), job.getStatus(), existing.getCandidateCount(),
                        List.of(), true, job.getCompletedAt());
            }
            throw new ApiException(HttpStatus.CONFLICT, "RESULT_ID_CONFLICT",
                    "A different result was already submitted for this job.");
        }
        if (!"RUNNING".equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT, "JOB_NOT_RUNNABLE",
                    "Only running recording analysis jobs can submit results.");
        }

        Recording recording = recordingMapper.findById(job.getRecordingId());
        if (recording == null) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                    "Recording analysis target was not found.");
        }
        Camera camera = cameraMapper.findById(recording.getCameraId()).orElseThrow(() ->
                new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "BUSINESS_RULE_VIOLATION",
                        "Recording camera was not found."));
        MediaServerPrincipal sourcePrincipal = new MediaServerPrincipal(
                camera.mediaServerId(), camera.cameraCode());

        List<CandidateEventCreateRequest> events = new ArrayList<>();
        for (int index = 0; index < request.candidates().size(); index++) {
            RecordingAnalysisBatchResultRequest.Candidate candidate = request.candidates().get(index);
            events.add(toEvent(job, camera, candidate, attempt, index));
        }
        List<Long> candidateIds = candidateService.createRecordingAnalysisBatch(
                sourcePrincipal, events, camera.id(), jobId, recording.getId());

        RecordingAnalysisResult result = new RecordingAnalysisResult();
        result.setJobId(jobId);
        result.setAttempt(attempt);
        result.setResultId(request.resultId());
        result.setPayloadHash(payloadHash);
        result.setStatus("SUCCEEDED");
        result.setCandidateCount(request.candidates().size());
        resultMapper.insert(result);
        if (jobMapper.markSucceeded(job.getCaseId(), jobId) != 1) {
            throw new ApiException(HttpStatus.CONFLICT, "RESOURCE_STATE_CONFLICT",
                    "Recording analysis job changed before completion.");
        }
        job.setStatus("SUCCEEDED");
        job.setCompletedAt(Instant.now());
        auditService.recordRequired(
                "RECORDING_ANALYSIS_JOB_SUCCEEDED", null, job.getCaseId(), "ANALYSIS_JOB", jobId,
                Map.of("workerId", workerId, "candidateCount", request.candidates().size()));
        return new RecordingAnalysisBatchResultResponse(
                jobId, request.resultId(), job.getStatus(), request.candidates().size(),
                List.copyOf(candidateIds), false, job.getCompletedAt());
    }

    private CandidateEventCreateRequest toEvent(
            AnalysisJob job, Camera camera, RecordingAnalysisBatchResultRequest.Candidate candidate,
            int attempt, int index) {
        String eventId = "analysis-" + job.getId() + "-attempt-" + attempt + "-candidate-" + index;
        return new CandidateEventCreateRequest(
                job.getCaseId(), camera.cameraCode(), eventId, candidate.detectedAt(), candidate.frameObjectKey(),
                List.of(new CandidateEventCreateRequest.Detection(
                        candidate.trackId(), candidate.similarity(), candidate.cropObjectKey(),
                        candidate.boundingBox().toCandidateBoundingBox())));
    }

    private void validateUniqueTracks(RecordingAnalysisBatchResultRequest request) {
        Set<String> tracks = new HashSet<>();
        for (RecordingAnalysisBatchResultRequest.Candidate candidate : request.candidates()) {
            if (!tracks.add(candidate.trackId())) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "DUPLICATE_TRACK_ID",
                        "Each trackId may appear only once in a recording result.");
            }
        }
    }

    private String payloadHash(RecordingAnalysisBatchResultRequest request) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(
                    request.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable", exception);
        }
    }
}
