package com.ssafy.eyesonu.recording.dto.aiworker;

import java.math.BigDecimal;
import java.time.Instant;

public record AiWorkerJobResponse(
        String schemaVersion,
        Long jobId,
        Long caseId,
        Long searchConditionId,
        Long recordingId,
        String modelKey,
        Long cameraId,
        String cameraName,
        String cameraAddress,
        String videoUrl,
        String referenceUrl,
        Instant recordingStart,
        Instant recordingEnd,
        String prompt,
        String exclusionPrompt,
        BigDecimal similarityThreshold,
        long searchFromMs,
        Long searchToMs,
        Instant leaseExpiresAt) {
}
