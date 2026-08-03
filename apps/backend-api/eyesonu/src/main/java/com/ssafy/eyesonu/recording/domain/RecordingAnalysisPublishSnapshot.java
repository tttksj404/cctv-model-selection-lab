package com.ssafy.eyesonu.recording.domain;

import java.math.BigDecimal;
import java.time.Instant;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
public class RecordingAnalysisPublishSnapshot {

    private Long jobId;
    private Long caseId;
    private Long recordingId;
    private Long cameraId;
    private String cameraCode;
    private String cameraName;
    private String recordingObjectKey;
    private String prompt;
    private String exclusionPrompt;
    private BigDecimal similarityThreshold;
    private Instant searchStart;
    private Instant searchEnd;
    private String searchArea;
    private int attempt;
}
