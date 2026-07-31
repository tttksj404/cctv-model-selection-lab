package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class CandidateAggregate {
    private Long id;
    private Long caseId;
    private Long cameraId;
    private String trackId;
    private Instant firstDetectedAt;
    private Instant lastDetectedAt;
    private BigDecimal bestSimilarity;
    private BigDecimal averageSimilarity;
    private Integer detectionCount;
    private BigDecimal similarity;
    private String cropObjectKey;
    private String frameObjectKey;
    private String boundingBox;
    private Integer version;
    private Instant createdAt;
}
