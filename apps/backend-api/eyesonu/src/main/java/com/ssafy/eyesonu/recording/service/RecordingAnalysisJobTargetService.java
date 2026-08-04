package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobTargetResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Duration;
import java.time.Instant;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingAnalysisJobTargetService {

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingMapper recordingMapper;
    private final StorageObjectUrlSigner urlSigner;
    private final RecordingAnalysisJobClaimService claimService;

    public RecordingAnalysisJobTargetService(
            AnalysisJobMapper analysisJobMapper,
            RecordingMapper recordingMapper,
            StorageObjectUrlSigner urlSigner,
            RecordingAnalysisJobClaimService claimService) {
        this.analysisJobMapper = analysisJobMapper;
        this.recordingMapper = recordingMapper;
        this.urlSigner = urlSigner;
        this.claimService = claimService;
    }

    public RecordingAnalysisJobTargetResponse find(
            Long jobId, String workerId, String claimToken) {
        AnalysisJob job = claimService.requireActiveWorkerJob(jobId, workerId, claimToken);

        var snapshot = analysisJobMapper.findRecordingAnalysisPublishSnapshot(jobId, job.getCaseId());
        if (snapshot == null) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                    "BUSINESS_RULE_VIOLATION", "Recording analysis target could not be loaded.");
        }
        Recording recording = recordingMapper.findById(snapshot.getRecordingId());
        if (recording == null || recording.getStartTime() == null || recording.getEndTime() == null
                || recording.getS3Key() == null || recording.getS3Key().isBlank()) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "BUSINESS_RULE_VIOLATION", "Recording source could not be loaded.");
        }
        Instant effectiveStart = laterOf(recording.getStartTime(), snapshot.getSearchStart());
        Instant effectiveEnd = earlierOf(recording.getEndTime(), snapshot.getSearchEnd());
        if (!effectiveStart.isBefore(effectiveEnd)) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_ENTITY,
                    "BUSINESS_RULE_VIOLATION", "Recording does not overlap the requested search window.");
        }
        String downloadUrl = signRecording(recording.getS3Key());
        return RecordingAnalysisJobTargetResponse.from(
                snapshot,
                job.getSearchConditionId(),
                downloadUrl,
                recording.getStartTime(),
                recording.getEndTime(),
                Duration.between(recording.getStartTime(), effectiveStart).toMillis(),
                Duration.between(recording.getStartTime(), effectiveEnd).toMillis());
    }

    private Instant laterOf(Instant recordingStart, Instant searchStart) {
        return searchStart != null && searchStart.isAfter(recordingStart) ? searchStart : recordingStart;
    }

    private Instant earlierOf(Instant recordingEnd, Instant searchEnd) {
        return searchEnd != null && searchEnd.isBefore(recordingEnd) ? searchEnd : recordingEnd;
    }

    private String signRecording(String objectKey) {
        try {
            return urlSigner.createGetUrl(objectKey);
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "STORAGE_UNAVAILABLE", "Recording download URL could not be created.");
        }
    }
}
