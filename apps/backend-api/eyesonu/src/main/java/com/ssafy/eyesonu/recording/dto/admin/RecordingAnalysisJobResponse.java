package com.ssafy.eyesonu.recording.dto.admin;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import java.time.Instant;

public record RecordingAnalysisJobResponse(
        Long jobId,
        Long caseId,
        Long conditionId,
        Long recordingId,
        String jobType,
        String status,
        String prompt,
        String exclusionPrompt,
        Instant searchStart,
        Instant searchEnd,
        String searchArea,
        Instant requestedAt) {

    public static RecordingAnalysisJobResponse from(AnalysisJob job) {
        return new RecordingAnalysisJobResponse(
                job.getId(), job.getCaseId(), job.getSearchConditionId(), job.getRecordingId(),
                job.getJobType(), job.getStatus(), job.getPromptSnapshot(),
                job.getExclusionPromptSnapshot(), job.getSearchStartSnapshot(),
                job.getSearchEndSnapshot(), job.getSearchAreaSnapshot(),
                job.getRequestedAt());
    }
}
