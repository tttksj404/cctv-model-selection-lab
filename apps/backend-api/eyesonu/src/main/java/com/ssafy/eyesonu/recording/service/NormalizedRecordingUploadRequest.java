package com.ssafy.eyesonu.recording.service;

import java.time.Instant;

public record NormalizedRecordingUploadRequest(
        String cameraCode,
        String idempotencyKey,
        Instant startTime,
        Instant endTime,
        String objectKey) {
}
