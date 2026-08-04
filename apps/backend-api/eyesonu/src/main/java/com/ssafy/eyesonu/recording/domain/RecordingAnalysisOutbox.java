package com.ssafy.eyesonu.recording.domain;

import java.time.Instant;
import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class RecordingAnalysisOutbox {

    private Long id;
    private String commandId;
    private String eventType;
    private Long jobId;
    private Long caseId;
    private Long recordingId;
    private Long cameraId;
    private String cameraCode;
    private String cameraName;
    private String recordingObjectKey;
    private String prompt;
    private String exclusionPrompt;
    private Instant searchStart;
    private Instant searchEnd;
    private String searchArea;
    private int attempt;
    private Instant occurredAt;
    private int retryCount;

    public RecordingAnalysisOutbox(
            Long id, String commandId, String eventType, Long jobId, Long caseId,
            Instant occurredAt, int retryCount) {
        this.id = id;
        this.commandId = commandId;
        this.eventType = eventType;
        this.jobId = jobId;
        this.caseId = caseId;
        this.attempt = 1;
        this.occurredAt = occurredAt;
        this.retryCount = retryCount;
    }
}
