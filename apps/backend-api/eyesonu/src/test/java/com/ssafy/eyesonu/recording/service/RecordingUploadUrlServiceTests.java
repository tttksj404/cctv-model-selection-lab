package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistrationResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateResponse;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class RecordingUploadUrlServiceTests {

    private static final long MEDIA_SERVER_ID = 7L;
    private static final String CAMERA_CODE = "camera-01";
    private static final String IDEMPOTENCY_KEY = "550e8400-e29b-41d4-a716-446655440000";
    private static final String OBJECT_KEY = "recordings/camera-01/2026/08/04/"
            + "20260804T031530123456Z_" + IDEMPOTENCY_KEY + ".mp4";

    private final CameraMapper cameraMapper = mock(CameraMapper.class);
    private final RecordingMapper recordingMapper = mock(RecordingMapper.class);
    private final StorageObjectUrlSigner urlSigner = mock(StorageObjectUrlSigner.class);
    private RecordingUploadUrlService service;

    @BeforeEach
    void setUp() {
        MinioProperties properties = new MinioProperties();
        properties.setMaxFileSizeBytes(104_857_600L);
        properties.setPresignedUrlExpiry(Duration.ofMinutes(15));
        service = new RecordingUploadUrlService(
                cameraMapper,
                recordingMapper,
                new RecordingRequestValidator(new RecordingObjectKeyFactory()),
                urlSigner,
                properties);
        when(cameraMapper.findByCameraCode(CAMERA_CODE)).thenReturn(Optional.of(
                new Camera(11L, MEDIA_SERVER_ID, CAMERA_CODE, "Camera")));
    }

    @Test
    void returnsServerOwnedKeyAndPublicPutUrl() {
        when(urlSigner.createPutUrl(OBJECT_KEY)).thenReturn("https://storage.example/signed");

        RecordingUploadUrlCreateResponse result = service.create(
                principal(), CAMERA_CODE, IDEMPOTENCY_KEY.toUpperCase(), request());

        assertEquals(OBJECT_KEY, result.objectKey());
        assertEquals("https://storage.example/signed", result.uploadUrl());
        assertEquals("video/mp4", result.contentType());
        assertEquals(900L, result.expiresInSeconds());
        assertEquals(104_857_600L, result.maxFileSizeBytes());
        verify(urlSigner).createPutUrl(OBJECT_KEY);
    }

    @Test
    void refreshesTheUrlForTheSameDeterministicObjectKey() {
        when(urlSigner.createPutUrl(OBJECT_KEY))
                .thenReturn("https://storage.example/first", "https://storage.example/second");

        RecordingUploadUrlCreateResponse first = service.create(
                principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());
        RecordingUploadUrlCreateResponse second = service.create(
                principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());

        assertEquals(first.objectKey(), second.objectKey());
        assertEquals("https://storage.example/first", first.uploadUrl());
        assertEquals("https://storage.example/second", second.uploadUrl());
        verify(urlSigner, org.mockito.Mockito.times(2)).createPutUrl(OBJECT_KEY);
    }

    @Test
    void rejectsMissingAuthenticationAndInvalidInputBeforeStorageAccess() {
        assertApiError("AUTHENTICATION_REQUIRED", 401,
                () -> service.create(null, CAMERA_CODE, IDEMPOTENCY_KEY, request()));
        assertApiError("VALIDATION_ERROR", 400,
                () -> service.create(principal(), CAMERA_CODE, "not-a-uuid", request()));
        assertApiError("VALIDATION_ERROR", 400,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY,
                        new RecordingUploadUrlCreateRequest(
                                OffsetDateTime.parse("2026-08-04T03:15:30Z"),
                                OffsetDateTime.parse("2026-08-04T03:15:30Z"))));
        verifyNoInteractions(urlSigner);
    }

    @Test
    void distinguishesMissingAndForeignCameras() {
        when(cameraMapper.findByCameraCode("camera-missing")).thenReturn(Optional.empty());
        when(cameraMapper.findByCameraCode("camera-foreign")).thenReturn(Optional.of(
                new Camera(12L, 999L, "camera-foreign", "Foreign")));

        assertApiError("RESOURCE_NOT_FOUND", 404, () -> service.create(
                principal(), "camera-missing", IDEMPOTENCY_KEY, request()));
        assertApiError("ACCESS_DENIED", 403, () -> service.create(
                principal(), "camera-foreign", IDEMPOTENCY_KEY, request()));
        verifyNoInteractions(urlSigner);
    }

    @Test
    void rejectsAnAlreadyRegisteredIdempotencyKeyWithoutSigning() {
        Recording recording = new Recording(
                99L, 11L, Instant.parse("2026-08-04T03:15:30.123456Z"),
                Instant.parse("2026-08-04T03:16:00.123456Z"), OBJECT_KEY, 50L, Instant.now());
        when(recordingMapper.findRegistrationByKey(MEDIA_SERVER_ID, IDEMPOTENCY_KEY))
                .thenReturn(new RecordingRegistrationResult(
                        MEDIA_SERVER_ID, IDEMPOTENCY_KEY, "0".repeat(64), recording));

        assertApiError("RECORDING_ALREADY_REGISTERED", 409,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));
        verify(urlSigner, never()).createPutUrl(OBJECT_KEY);
    }

    @Test
    void mapsSigningFailureToStorageUnavailable() {
        when(urlSigner.createPutUrl(OBJECT_KEY)).thenThrow(new StorageObjectUnavailableException(null));

        assertApiError("STORAGE_UNAVAILABLE", 503,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));
    }

    private MediaServerPrincipal principal() {
        return new MediaServerPrincipal(MEDIA_SERVER_ID, "rpi5-media-01");
    }

    private RecordingUploadUrlCreateRequest request() {
        return new RecordingUploadUrlCreateRequest(
                OffsetDateTime.parse("2026-08-04T12:15:30.123456+09:00"),
                OffsetDateTime.parse("2026-08-04T12:16:00.123456+09:00"));
    }

    private void assertApiError(String code, int status, Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals(code, exception.getCode());
        assertEquals(status, exception.getStatus().value());
    }
}
