package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import java.time.Instant;

public record RecordingAnalysisJobTargetResponse(
        Long jobId,
        Long caseId,
        Long recordingId,
        Long cameraId,
        String cameraCode,
        String cameraName,
        String recordingObjectKey,
        String prompt,
        String exclusionPrompt,
        Instant searchStart,
        Instant searchEnd,
        String searchArea,
        int attempt) {

    public static RecordingAnalysisJobTargetResponse from(RecordingAnalysisPublishSnapshot snapshot) {
        return new RecordingAnalysisJobTargetResponse(
                snapshot.getJobId(), snapshot.getCaseId(), snapshot.getRecordingId(), snapshot.getCameraId(),
                snapshot.getCameraCode(), snapshot.getCameraName(), snapshot.getRecordingObjectKey(),
                snapshot.getPrompt(), snapshot.getExclusionPrompt(), snapshot.getSearchStart(),
                snapshot.getSearchEnd(), snapshot.getSearchArea(), snapshot.getAttempt());
    }
}
