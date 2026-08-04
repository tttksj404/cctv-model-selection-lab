package com.ssafy.eyesonu.recording.dto.device;

import java.time.Instant;

public record RecordingAnalysisWorkerHeartbeatResponse(
        Long jobId,
        String status,
        Instant claimExpiresAt) {

    public static RecordingAnalysisWorkerHeartbeatResponse running(
            Long jobId, Instant claimExpiresAt) {
        return new RecordingAnalysisWorkerHeartbeatResponse(jobId, "RUNNING", claimExpiresAt);
    }
}
