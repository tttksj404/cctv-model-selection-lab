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
public class RecordingRegistration {

    private Long mediaServerId;
    private String idempotencyKey;
    private String requestFingerprint;
    private Long recordingId;
    private Instant createdAt;
}
