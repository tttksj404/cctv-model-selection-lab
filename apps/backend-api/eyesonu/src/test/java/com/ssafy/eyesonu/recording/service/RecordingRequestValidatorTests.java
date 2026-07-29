package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import java.time.Instant;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.Test;

class RecordingRequestValidatorTests {

    private static final String CAMERA_CODE = "CAM-001";
    private static final String KEY = "550e8400-e29b-41d4-a716-446655440000";

    private final RecordingRequestValidator validator = new RecordingRequestValidator();

    @Test
    void normalizesUuidAndEquivalentOffsetsBeforeFingerprinting() {
        RecordingCreateRequest kst = request(
                "2026-07-20T10:00:00.123456+09:00",
                "2026-07-20T10:01:00.123456+09:00",
                objectKey("video.mp4"));
        RecordingCreateRequest utc = request(
                "2026-07-20T01:00:00.123456Z",
                "2026-07-20T01:01:00.123456Z",
                objectKey("video.mp4"));

        NormalizedRecordingCreateRequest first = validator.validate(
                CAMERA_CODE, KEY.toUpperCase(), kst);
        NormalizedRecordingCreateRequest second = validator.validate(CAMERA_CODE, KEY, utc);

        assertEquals(KEY, first.idempotencyKey());
        assertEquals(Instant.parse("2026-07-20T01:00:00.123456Z"), first.startTime());
        assertEquals(first.requestFingerprint(), second.requestFingerprint());
        assertEquals(64, first.requestFingerprint().length());
    }

    @Test
    void rejectsInvalidUuidTimeRangeAndExcessPrecision() {
        assertValidation(() -> validator.validate(CAMERA_CODE, "not-a-uuid", validRequest()));
        assertValidation(() -> validator.validate(CAMERA_CODE, KEY, request(
                "2026-07-20T01:00:00Z", "2026-07-20T01:00:00Z", objectKey("video.mp4"))));
        assertValidation(() -> validator.validate(CAMERA_CODE, KEY, request(
                "2026-07-20T01:00:00.1234567Z",
                "2026-07-20T01:01:00Z",
                objectKey("video.mp4"))));
    }

    @Test
    void rejectsUnsafeOrMismatchedObjectKeys() {
        String[] invalidKeys = {
                "recordings/OTHER/video.mp4",
                objectKey("video.MP4"),
                objectKey(".mp4"),
                "recordings/CAM-001//video.mp4",
                "recordings/CAM-001/./video.mp4",
                "recordings/CAM-001/../video.mp4",
                "recordings/CAM-001/folder\\video.mp4",
                "recordings/CAM-001/video\n.mp4",
                objectKey("a".repeat(500) + ".mp4")
        };

        for (String invalidKey : invalidKeys) {
            assertValidation(() -> validator.validate(
                    CAMERA_CODE,
                    KEY,
                    request("2026-07-20T01:00:00Z", "2026-07-20T01:01:00Z", invalidKey)));
        }
    }

    private RecordingCreateRequest validRequest() {
        return request(
                "2026-07-20T01:00:00Z",
                "2026-07-20T01:01:00Z",
                objectKey("video.mp4"));
    }

    private RecordingCreateRequest request(String start, String end, String objectKey) {
        return new RecordingCreateRequest(
                OffsetDateTime.parse(start),
                OffsetDateTime.parse(end),
                objectKey);
    }

    private String objectKey(String fileName) {
        return "recordings/" + CAMERA_CODE + "/" + fileName;
    }

    private void assertValidation(Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals("VALIDATION_ERROR", exception.getCode());
        assertEquals(400, exception.getStatus().value());
    }
}
