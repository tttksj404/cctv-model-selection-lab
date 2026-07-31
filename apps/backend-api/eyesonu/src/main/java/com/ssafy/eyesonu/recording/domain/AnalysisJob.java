package com.ssafy.eyesonu.recording.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class AnalysisJob {

    private Long id;
    private Long caseId;
    private Long searchConditionId;
    private Long recordingId;
    private String jobType;
    private String status;
    private String promptSnapshot;
    private String exclusionPromptSnapshot;
    private Instant searchStartSnapshot;
    private Instant searchEndSnapshot;
    private String searchAreaSnapshot;
    private BigDecimal similarityThresholdSnapshot;
    private int retryCount;
    private String errorMessage;
    private Instant requestedAt;
    private Instant startedAt;
    private Instant completedAt;
}
