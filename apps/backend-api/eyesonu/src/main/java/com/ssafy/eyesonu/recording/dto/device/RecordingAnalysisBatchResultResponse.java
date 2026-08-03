package com.ssafy.eyesonu.recording.dto.device;

import java.time.Instant;
import java.util.List;

public record RecordingAnalysisBatchResultResponse(
        Long jobId,
        String resultId,
        String status,
        int candidateCount,
        List<Long> candidateIds,
        boolean duplicate,
        Instant completedAt) {
}
