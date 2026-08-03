package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class AdminCandidateRow {
    private Long id;
    private Long caseId;
    private String caseNumber;
    private String missingName;
    private Long cameraId;
    private String cameraCode;
    private String cameraName;
    private CandidateSourceType sourceType;
    private Long analysisJobId;
    private Long recordingId;
    private String dedupeScope;
    private String trackId;
    private Instant firstDetectedAt;
    private Instant lastDetectedAt;
    private BigDecimal bestSimilarity;
    private BigDecimal averageSimilarity;
    private Integer detectionCount;
    private String frameObjectKey;
    private String cropObjectKey;
    private String boundingBox;
    private String reviewStatus;
    private String reviewComment;
    private Long version;
    private Instant createdAt;
    private Instant updatedAt;
}
