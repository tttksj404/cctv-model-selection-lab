package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import java.time.Instant;
import java.time.OffsetDateTime;
import org.junit.jupiter.api.Test;

class RecordingRequestValidatorTests {

    private static final String CAMERA_CODE = "camera-01";
    private static final String KEY = "550e8400-e29b-41d4-a716-446655440000";
    private static final String OBJECT_KEY =
            "recordings/camera-01/2026/07/20/20260720T010000123456Z_" + KEY + ".mp4";

    private final RecordingRequestValidator validator =
            new RecordingRequestValidator(new RecordingObjectKeyFactory());

    @Test
    void normalizesUuidAndEquivalentOffsetsBeforeFingerprinting() {
        RecordingCreateRequest kst = request(
                "2026-07-20T10:00:00.123456+09:00",
                "2026-07-20T10:01:00.123456+09:00",
                OBJECT_KEY);
        RecordingCreateRequest utc = request(
                "2026-07-20T01:00:00.123456Z",
                "2026-07-20T01:01:00.123456Z",
                OBJECT_KEY);

        NormalizedRecordingCreateRequest first = validator.validate(
                CAMERA_CODE, KEY.toUpperCase(), kst);
        NormalizedRecordingCreateRequest second = validator.validate(CAMERA_CODE, KEY, utc);

        assertEquals(KEY, first.idempotencyKey());
        assertEquals(Instant.parse("2026-07-20T01:00:00.123456Z"), first.startTime());
        assertEquals(first.requestFingerprint(), second.requestFingerprint());
        assertEquals(64, first.requestFingerprint().length());
    }

    @Test
    void createsTheSameServerOwnedKeyForEquivalentUploadTimes() {
        var kst = validator.validateUpload(
                CAMERA_CODE,
                KEY.toUpperCase(),
                new com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest(
                        OffsetDateTime.parse("2026-07-20T10:00:00.123456+09:00"),
                        OffsetDateTime.parse("2026-07-20T10:00:30.123456+09:00")));
        var utc = validator.validateUpload(
                CAMERA_CODE,
                KEY,
                new com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest(
                        OffsetDateTime.parse("2026-07-20T01:00:00.123456Z"),
                        OffsetDateTime.parse("2026-07-20T01:00:30.123456Z")));

        assertEquals(OBJECT_KEY, kst.objectKey());
        assertEquals(kst, utc);
    }

    @Test
    void rejectsInvalidUuidTimeRangeAndExcessPrecision() {
        assertValidation(() -> validator.validate(CAMERA_CODE, "not-a-uuid", validRequest()));
        assertValidation(() -> validator.validate(CAMERA_CODE, KEY, request(
                "2026-07-20T01:00:00Z", "2026-07-20T01:00:00Z", OBJECT_KEY)));
        assertValidation(() -> validator.validate(CAMERA_CODE, KEY, request(
                "2026-07-20T01:00:00.1234567Z",
                "2026-07-20T01:01:00Z",
                OBJECT_KEY)));
    }

    @Test
    void rejectsUnsafeOrMismatchedObjectKeys() {
        String[] invalidKeys = {"recordings/camera-01/video.mp4", OBJECT_KEY.toUpperCase(), "x".repeat(501)};

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
                OBJECT_KEY);
    }

    private RecordingCreateRequest request(String start, String end, String objectKey) {
        return new RecordingCreateRequest(
                OffsetDateTime.parse(start),
                OffsetDateTime.parse(end),
                objectKey);
    }

    private void assertValidation(Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals("VALIDATION_ERROR", exception.getCode());
        assertEquals(400, exception.getStatus().value());
    }
}
