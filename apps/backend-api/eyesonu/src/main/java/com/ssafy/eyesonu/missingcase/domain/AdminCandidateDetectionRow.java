package com.ssafy.eyesonu.missingcase.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class AdminCandidateDetectionRow {
    private Long id;
    private String eventId;
    private Instant detectedAt;
    private String frameObjectKey;
    private String trackId;
    private String cropObjectKey;
    private BigDecimal similarity;
    private String boundingBox;
}
