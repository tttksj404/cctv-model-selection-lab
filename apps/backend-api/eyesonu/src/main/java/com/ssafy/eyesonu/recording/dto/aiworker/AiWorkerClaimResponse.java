package com.ssafy.eyesonu.recording.dto.aiworker;

import java.time.Instant;

public record AiWorkerClaimResponse(
        String schemaVersion,
        AiWorkerJobResponse job,
        String leaseToken,
        Instant leaseExpiresAt,
        int pollAfterMs) {

    public static AiWorkerClaimResponse empty(String schemaVersion, int pollAfterMs) {
        return new AiWorkerClaimResponse(schemaVersion, null, null, null, pollAfterMs);
    }
}
