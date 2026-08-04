package com.ssafy.eyesonu.recording.dto.device;

public record RecordingUploadUrlCreateResponse(
        String objectKey,
        String uploadUrl,
        String contentType,
        long expiresInSeconds,
        long maxFileSizeBytes) {
}
