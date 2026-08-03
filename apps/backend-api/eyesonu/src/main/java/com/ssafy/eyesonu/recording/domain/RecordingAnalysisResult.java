package com.ssafy.eyesonu.recording.domain;

import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class RecordingAnalysisResult {
    private Long id;
    private Long jobId;
    private String resultId;
    private String payloadHash;
    private int candidateCount;
    private Instant receivedAt;
}
