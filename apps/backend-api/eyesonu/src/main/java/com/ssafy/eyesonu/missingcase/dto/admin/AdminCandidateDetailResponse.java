package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import com.ssafy.eyesonu.missingcase.domain.CandidateSourceType;
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
        CandidateSourceType sourceType,
        Long analysisJobId,
        Long recordingId,
        String trackId,
        Instant firstDetectedAt,
        Instant lastDetectedAt,
        BigDecimal bestSimilarity,
        BigDecimal averageSimilarity,
        Integer detectionCount,
        String frameUrl,
        String cropUrl,
        String boundingBox,
        String reviewStatus,
        String reviewComment,
        Long version,
        Instant createdAt,
        Instant updatedAt,
        List<AdminCandidateDetectionResponse> detections) {

    public static AdminCandidateDetailResponse from(AdminCandidateRow row, String frameUrl, String cropUrl,
                                                     List<AdminCandidateDetectionResponse> detections) {
        return new AdminCandidateDetailResponse(row.getId(), row.getCaseId(), row.getCaseNumber(), row.getMissingName(),
                row.getCameraId(), row.getCameraCode(), row.getCameraName(), row.getSourceType(),
                row.getAnalysisJobId(), row.getRecordingId(), row.getTrackId(), row.getFirstDetectedAt(),
                row.getLastDetectedAt(), row.getBestSimilarity(), row.getAverageSimilarity(), row.getDetectionCount(),
                frameUrl, cropUrl, row.getBoundingBox(), row.getReviewStatus(),
                row.getReviewComment(), row.getVersion(),
                row.getCreatedAt(), row.getUpdatedAt(), detections);
    }
}
