package com.ssafy.eyesonu.missingcase.dto.device;

import java.time.Instant;
import java.util.List;

public record CandidateEventCreateResponse(
        String eventId,
        Long caseId,
        Long cameraId,
        int detectionCount,
        List<Long> candidateIds,
        boolean duplicate,
        Instant createdAt) {
}
