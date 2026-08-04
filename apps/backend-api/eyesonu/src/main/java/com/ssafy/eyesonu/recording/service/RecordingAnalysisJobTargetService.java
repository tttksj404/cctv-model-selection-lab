package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobTargetResponse;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingAnalysisJobTargetService {

    private final AnalysisJobMapper analysisJobMapper;

    public RecordingAnalysisJobTargetService(AnalysisJobMapper analysisJobMapper) {
        this.analysisJobMapper = analysisJobMapper;
    }

    public RecordingAnalysisJobTargetResponse find(Long jobId, String workerId) {
        if (workerId == null || workerId.isBlank()) {
            throw new ApiException(HttpStatus.UNAUTHORIZED,
                    "AUTHENTICATION_REQUIRED", "Authenticated worker is required.");
        }

        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND,
                    "RESOURCE_NOT_FOUND", "Recording analysis job was not found.");
        }
        if (!"RUNNING".equals(job.getStatus())) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "JOB_NOT_RUNNABLE", "Only running recording analysis jobs can read the target.");
        }
        if (!Objects.equals(job.getClaimedBy(), workerId)) {
            throw new ApiException(HttpStatus.CONFLICT,
                    "JOB_NOT_CLAIMED", "Recording analysis job is claimed by another worker.");
        }

        var snapshot = analysisJobMapper.findRecordingAnalysisPublishSnapshot(jobId, job.getCaseId());
        if (snapshot == null) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT,
                    "BUSINESS_RULE_VIOLATION", "Recording analysis target could not be loaded.");
        }
        return RecordingAnalysisJobTargetResponse.from(snapshot);
    }
}
