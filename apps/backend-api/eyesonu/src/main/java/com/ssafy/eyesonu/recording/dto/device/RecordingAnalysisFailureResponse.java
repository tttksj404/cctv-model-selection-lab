package com.ssafy.eyesonu.recording.dto.device;

import java.time.Instant;

public record RecordingAnalysisFailureResponse(
        Long jobId,
        String resultId,
        String status,
        int attempt,
        boolean duplicate,
        Instant completedAt) {
}
