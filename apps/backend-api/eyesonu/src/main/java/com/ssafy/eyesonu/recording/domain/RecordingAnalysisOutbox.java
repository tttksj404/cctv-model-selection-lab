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
    private Instant occurredAt;
    private int retryCount;
}
