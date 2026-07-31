package com.ssafy.eyesonu.missingcase.domain;

import java.time.Instant;
import lombok.Getter;
import lombok.Setter;

@Getter
@Setter
public class CandidateEvent {
    private Long id;
    private String eventId;
    private Long caseId;
    private Long cameraId;
    private Instant detectedAt;
    private String frameObjectKey;
    private Instant createdAt;
}
