package com.ssafy.eyesonu.recording.domain;

import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RecordingAnalysisResult {
    private Long id;
    private Long jobId;
    private int attempt;
    private String resultId;
    private String payloadHash;
    private String status;
    private int candidateCount;
    private String errorCode;
    private String errorMessage;
    private Instant receivedAt;
}
