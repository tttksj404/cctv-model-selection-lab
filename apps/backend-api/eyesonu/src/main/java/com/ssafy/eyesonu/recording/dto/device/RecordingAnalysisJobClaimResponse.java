package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimResult;
import java.time.Instant;

public record RecordingAnalysisJobClaimResponse(
        Long jobId,
        String status,
        int attempt,
        boolean duplicate,
        Instant startedAt,
        String claimedBy,
        Instant claimExpiresAt) {

    public static RecordingAnalysisJobClaimResponse from(RecordingAnalysisJobClaimResult result) {
        return new RecordingAnalysisJobClaimResponse(
                result.job().getId(), result.job().getStatus(), result.job().getRetryCount() + 1,
                result.duplicate(), result.job().getStartedAt(),
                result.job().getClaimedBy(), result.job().getClaimExpiresAt());
    }
}
