package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;

public record AdminCandidateDetailResponse(
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
        String reviewComment,
        Long version,
        Instant createdAt,
        Instant updatedAt,
        List<AdminCandidateDetectionResponse> detections) {

    public static AdminCandidateDetailResponse from(AdminCandidateRow row,
                                                     List<AdminCandidateDetectionResponse> detections) {
        return new AdminCandidateDetailResponse(row.getId(), row.getCaseId(), row.getCaseNumber(), row.getMissingName(),
                row.getCameraId(), row.getCameraCode(), row.getCameraName(), row.getTrackId(), row.getFirstDetectedAt(),
                row.getLastDetectedAt(), row.getBestSimilarity(), row.getAverageSimilarity(), row.getDetectionCount(),
                row.getFrameObjectKey(), row.getCropObjectKey(), row.getBoundingBox(), row.getReviewStatus(),
                row.getReviewComment(), row.getVersion(),
                row.getCreatedAt(), row.getUpdatedAt(), detections);
    }
}
