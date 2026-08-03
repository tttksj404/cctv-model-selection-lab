package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateDetectionRow;
import java.math.BigDecimal;
import java.time.Instant;

public record AdminCandidateDetectionResponse(
        String eventId,
        Instant detectedAt,
        String trackId,
        String cropUrl,
        BigDecimal similarity,
        String boundingBox) {

    public static AdminCandidateDetectionResponse from(AdminCandidateDetectionRow row, String cropUrl) {
        return new AdminCandidateDetectionResponse(row.getEventId(), row.getDetectedAt(),
                row.getTrackId(), cropUrl, row.getSimilarity(), row.getBoundingBox());
    }
}
