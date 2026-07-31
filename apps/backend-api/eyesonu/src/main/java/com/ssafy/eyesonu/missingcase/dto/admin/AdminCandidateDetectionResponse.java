package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateDetectionRow;
import java.math.BigDecimal;
import java.time.Instant;

public record AdminCandidateDetectionResponse(
        String eventId,
        Instant detectedAt,
        String frameObjectKey,
        String trackId,
        String cropObjectKey,
        BigDecimal similarity,
        String boundingBox) {

    public static AdminCandidateDetectionResponse from(AdminCandidateDetectionRow row) {
        return new AdminCandidateDetectionResponse(row.getEventId(), row.getDetectedAt(), row.getFrameObjectKey(),
                row.getTrackId(), row.getCropObjectKey(), row.getSimilarity(), row.getBoundingBox());
    }
}
