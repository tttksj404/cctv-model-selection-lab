package com.ssafy.eyesonu.recording.service;

import java.time.Instant;

public record NormalizedRecordingCreateRequest(
        String cameraCode,
        String idempotencyKey,
        Instant startTime,
        Instant endTime,
        String objectKey,
        String requestFingerprint) {
}
