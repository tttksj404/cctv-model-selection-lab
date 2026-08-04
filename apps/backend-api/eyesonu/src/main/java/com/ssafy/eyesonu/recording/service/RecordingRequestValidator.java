package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest;
import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.HexFormat;
import java.util.UUID;
import java.util.regex.Pattern;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class RecordingRequestValidator {

    private static final int MAX_OBJECT_KEY_LENGTH = 500;
    private static final Pattern UUID_PATTERN = Pattern.compile(
            "^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$");

    private final RecordingObjectKeyFactory objectKeyFactory;

    public RecordingRequestValidator(RecordingObjectKeyFactory objectKeyFactory) {
        this.objectKeyFactory = objectKeyFactory;
    }

    public NormalizedRecordingCreateRequest validate(
            String cameraCode, String idempotencyKey, RecordingCreateRequest request) {
        if (request == null) {
            throw validationError("Request body is required");
        }
        if (cameraCode == null || cameraCode.isBlank()) {
            throw validationError("cameraCode is required");
        }

        NormalizedRecordingUploadRequest uploadRequest = normalize(
                cameraCode, idempotencyKey, request.startTime(), request.endTime());
        validateObjectKey(uploadRequest.objectKey(), request.objectKey());

        return new NormalizedRecordingCreateRequest(
                uploadRequest.cameraCode(),
                uploadRequest.idempotencyKey(),
                uploadRequest.startTime(),
                uploadRequest.endTime(),
                request.objectKey(),
                fingerprint(
                        uploadRequest.cameraCode(),
                        uploadRequest.startTime(),
                        uploadRequest.endTime(),
                        request.objectKey()));
    }

    public NormalizedRecordingUploadRequest validateUpload(
            String cameraCode,
            String idempotencyKey,
            RecordingUploadUrlCreateRequest request) {
        if (request == null) {
            throw validationError("Request body is required");
        }
        return normalize(cameraCode, idempotencyKey, request.startTime(), request.endTime());
    }

    public Instant normalizeQueryTime(OffsetDateTime value, String fieldName) {
        if (value == null) {
            return null;
        }
        return normalizeTime(value, fieldName);
    }

    private NormalizedRecordingUploadRequest normalize(
            String cameraCode,
            String idempotencyKey,
            OffsetDateTime startTimeValue,
            OffsetDateTime endTimeValue) {
        if (cameraCode == null || cameraCode.isBlank()) {
            throw validationError("cameraCode is required");
        }
        String normalizedKey = normalizeIdempotencyKey(idempotencyKey);
        Instant startTime = normalizeTime(startTimeValue, "startTime");
        Instant endTime = normalizeTime(endTimeValue, "endTime");
        if (!endTime.isAfter(startTime)) {
            throw validationError("endTime must be after startTime");
        }
        return new NormalizedRecordingUploadRequest(
                cameraCode,
                normalizedKey,
                startTime,
                endTime,
                objectKeyFactory.create(cameraCode, startTime, normalizedKey));
    }

    private String normalizeIdempotencyKey(String value) {
        if (value == null || !UUID_PATTERN.matcher(value).matches()) {
            throw validationError("Idempotency-Key must be a canonical UUID");
        }
        try {
            return UUID.fromString(value).toString();
        } catch (IllegalArgumentException exception) {
            throw validationError("Idempotency-Key must be a canonical UUID");
        }
    }

    private Instant normalizeTime(OffsetDateTime value, String fieldName) {
        if (value == null) {
            throw validationError(fieldName + " is required");
        }
        if (value.getNano() % 1_000 != 0) {
            throw validationError(fieldName + " must have at most 6 fractional digits");
        }
        return value.toInstant();
    }

    private void validateObjectKey(String expectedObjectKey, String objectKey) {
        if (objectKey == null || objectKey.isBlank()) {
            throw validationError("objectKey is required");
        }
        if (objectKey.codePointCount(0, objectKey.length()) > MAX_OBJECT_KEY_LENGTH) {
            throw validationError("objectKey must not exceed 500 characters");
        }
        if (!expectedObjectKey.equals(objectKey)) {
            throw validationError("objectKey must match the server-issued recording object key");
        }
    }

    private String fingerprint(String cameraCode, Instant startTime, Instant endTime, String objectKey) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            updateLengthPrefixed(digest, cameraCode.getBytes(StandardCharsets.UTF_8));
            updateLengthPrefixed(digest, startTime.toString().getBytes(StandardCharsets.UTF_8));
            updateLengthPrefixed(digest, endTime.toString().getBytes(StandardCharsets.UTF_8));
            updateLengthPrefixed(digest, objectKey.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest.digest());
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available", exception);
        }
    }

    private void updateLengthPrefixed(MessageDigest digest, byte[] value) {
        digest.update(ByteBuffer.allocate(Integer.BYTES).putInt(value.length).array());
        digest.update(value);
    }

    private ApiException validationError(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }
}
