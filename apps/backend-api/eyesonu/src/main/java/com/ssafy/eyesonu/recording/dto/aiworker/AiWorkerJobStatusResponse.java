package com.ssafy.eyesonu.recording.dto.aiworker;

public record AiWorkerJobStatusResponse(
        String schemaVersion,
        Long jobId,
        String status,
        String workerId,
        String resultModelKey,
        String resultDigest) {
}
