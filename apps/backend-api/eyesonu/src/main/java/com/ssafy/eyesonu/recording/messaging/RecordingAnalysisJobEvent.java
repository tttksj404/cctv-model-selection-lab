package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.math.BigDecimal;

public record RecordingAnalysisJobEvent(
        String commandId,
        String eventType,
        Long jobId,
        Long caseId,
        Long recordingId,
        Long cameraId,
        String cameraCode,
        String cameraName,
        String recordingObjectKey,
        String prompt,
        String exclusionPrompt,
        BigDecimal similarityThreshold,
        Instant searchStart,
        Instant searchEnd,
        String searchArea,
        int attempt,
        Instant occurredAt) {

    public RecordingAnalysisJobEvent(
            String commandId, String eventType, Long jobId, Long caseId, Instant occurredAt) {
        this(commandId, eventType, jobId, caseId, null, null, null, null, null,
                null, null, null, null, null, null, 1, occurredAt);
    }
}
