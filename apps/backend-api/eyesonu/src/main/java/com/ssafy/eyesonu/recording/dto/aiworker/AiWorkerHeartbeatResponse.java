package com.ssafy.eyesonu.recording.dto.aiworker;

import java.time.Instant;

public record AiWorkerHeartbeatResponse(
        String schemaVersion,
        Long jobId,
        String status,
        Instant leaseExpiresAt) {
}
