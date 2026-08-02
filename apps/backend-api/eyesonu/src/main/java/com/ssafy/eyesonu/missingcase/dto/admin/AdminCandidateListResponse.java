package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import java.math.BigDecimal;
import java.time.Instant;

public record AdminCandidateListResponse(
        Long id,
        Long caseId,
        String caseNumber,
        String missingName,
        Long cameraId,
        String cameraCode,
        String cameraName,
        String trackId,
        Instant firstDetectedAt,
        Instant lastDetectedAt,
        BigDecimal bestSimilarity,
        BigDecimal averageSimilarity,
        Integer detectionCount,
        String frameObjectKey,
        String cropObjectKey,
        String boundingBox,
        String reviewStatus,
        Long version,
        Instant createdAt,
        Instant updatedAt) {

    public static AdminCandidateListResponse from(AdminCandidateRow row) {
        return new AdminCandidateListResponse(row.getId(), row.getCaseId(), row.getCaseNumber(), row.getMissingName(),
                row.getCameraId(), row.getCameraCode(), row.getCameraName(), row.getTrackId(), row.getFirstDetectedAt(),
                row.getLastDetectedAt(), row.getBestSimilarity(), row.getAverageSimilarity(), row.getDetectionCount(),
                row.getFrameObjectKey(), row.getCropObjectKey(), row.getBoundingBox(), row.getReviewStatus(), row.getVersion(),
                row.getCreatedAt(), row.getUpdatedAt());
    }
}
