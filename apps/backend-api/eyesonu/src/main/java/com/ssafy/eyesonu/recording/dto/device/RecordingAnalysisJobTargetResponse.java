package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import java.time.Instant;

public record RecordingAnalysisJobTargetResponse(
        Long jobId,
        Long caseId,
        Long searchConditionId,
        Long recordingId,
        Long cameraId,
        String cameraCode,
        String cameraName,
        String recordingObjectKey,
        String recordingDownloadUrl,
        Instant recordingStart,
        Instant recordingEnd,
        String prompt,
        String exclusionPrompt,
        Instant searchStart,
        Instant searchEnd,
        String searchArea,
        long searchFromMs,
        long searchToMs,
        int attempt) {

    public static RecordingAnalysisJobTargetResponse from(
            RecordingAnalysisPublishSnapshot snapshot,
            Long searchConditionId,
            String recordingDownloadUrl,
            Instant recordingStart,
            Instant recordingEnd,
            long searchFromMs,
            long searchToMs) {
        return new RecordingAnalysisJobTargetResponse(
                snapshot.getJobId(), snapshot.getCaseId(), searchConditionId, snapshot.getRecordingId(),
                snapshot.getCameraId(),
                snapshot.getCameraCode(), snapshot.getCameraName(), snapshot.getRecordingObjectKey(),
                recordingDownloadUrl, recordingStart, recordingEnd,
                snapshot.getPrompt(), snapshot.getExclusionPrompt(), snapshot.getSearchStart(),
                snapshot.getSearchEnd(), snapshot.getSearchArea(), searchFromMs, searchToMs,
                snapshot.getAttempt());
    }
}
