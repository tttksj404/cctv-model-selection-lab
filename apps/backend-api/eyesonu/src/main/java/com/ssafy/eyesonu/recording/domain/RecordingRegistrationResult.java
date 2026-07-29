package com.ssafy.eyesonu.recording.domain;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;

@Getter
@Setter
@NoArgsConstructor
@AllArgsConstructor
public class RecordingRegistrationResult {

    private Long mediaServerId;
    private String idempotencyKey;
    private String requestFingerprint;
    private Recording recording;
}
