package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.doThrow;
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
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.transaction.support.TransactionSynchronizationManager;

class RecordingCommandServiceTests {

    private static final long MEDIA_SERVER_ID = 7L;
    private static final long CAMERA_ID = 11L;
    private static final String CAMERA_CODE = "CAM-001";
    private static final String IDEMPOTENCY_KEY = "550e8400-e29b-41d4-a716-446655440000";
    private static final String OBJECT_KEY = "recordings/CAM-001/2026/video.mp4";
    private static final long MAX_FILE_SIZE = 5_368_709_120L;

    private final CameraMapper cameraMapper = mock(CameraMapper.class);
    private final RecordingMapper recordingMapper = mock(RecordingMapper.class);
    private final StorageObjectVerifier storageVerifier = mock(StorageObjectVerifier.class);
    private final RecordingRegistrationWriter writer = mock(RecordingRegistrationWriter.class);
    private final RecordingRequestValidator validator = new RecordingRequestValidator();

    private RecordingCommandService service;

    @BeforeEach
    void setUp() {
        MinioProperties properties = new MinioProperties();
        properties.setMaxFileSizeBytes(MAX_FILE_SIZE);
        service = new RecordingCommandService(
                cameraMapper, recordingMapper, validator, storageVerifier, writer, properties);
        when(cameraMapper.findByCameraCode(CAMERA_CODE)).thenReturn(Optional.of(
                new Camera(CAMERA_ID, MEDIA_SERVER_ID, CAMERA_CODE, "Camera")));
    }

    @Test
    void createsFromVerifiedSizeWithStorageCallOutsideTransaction() {
        Recording persisted = recording(99L, 80L);
        when(storageVerifier.stat(OBJECT_KEY)).thenAnswer(invocation -> {
            assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
            return new StorageObject(80L, "video/mp4");
        });
        when(writer.create(eq(MEDIA_SERVER_ID), any(NormalizedRecordingCreateRequest.class), eq(80L)))
                .thenReturn(persisted);

        RecordingCreateResult result = service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());

        assertFalse(result.duplicate());
        assertSame(persisted, result.recording());
        verify(storageVerifier).stat(OBJECT_KEY);
        verify(writer).create(eq(MEDIA_SERVER_ID), any(NormalizedRecordingCreateRequest.class), eq(80L));
    }

    @Test
    void successfulReplayReturnsExistingResultWithoutStatOrWrite() {
        NormalizedRecordingCreateRequest normalized = validator.validate(
                CAMERA_CODE, IDEMPOTENCY_KEY, request());
        Recording persisted = recording(99L, 80L);
        when(recordingMapper.findRegistrationByKey(MEDIA_SERVER_ID, IDEMPOTENCY_KEY))
                .thenReturn(new RecordingRegistrationResult(
                        MEDIA_SERVER_ID, IDEMPOTENCY_KEY, normalized.requestFingerprint(), persisted));

        RecordingCreateResult result = service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());

        assertTrue(result.duplicate());
        assertSame(persisted, result.recording());
        verifyNoInteractions(storageVerifier, writer);
        verify(recordingMapper, never()).findByS3Key(any());
    }

    @Test
    void rejectsReusedIdempotencyKeyWithDifferentFingerprint() {
        when(recordingMapper.findRegistrationByKey(MEDIA_SERVER_ID, IDEMPOTENCY_KEY))
                .thenReturn(new RecordingRegistrationResult(
                        MEDIA_SERVER_ID, IDEMPOTENCY_KEY, "0".repeat(64), recording(99L, 80L)));

        assertApiError(
                "IDEMPOTENCY_KEY_CONFLICT",
                409,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));
        verifyNoInteractions(storageVerifier, writer);
    }

    @Test
    void distinguishesMissingAndForeignCameras() {
        when(cameraMapper.findByCameraCode("MISSING")).thenReturn(Optional.empty());
        when(cameraMapper.findByCameraCode("FOREIGN")).thenReturn(Optional.of(
                new Camera(12L, 999L, "FOREIGN", "Foreign")));

        assertApiError("RESOURCE_NOT_FOUND", 404, () -> service.create(
                principal(), "MISSING", IDEMPOTENCY_KEY,
                requestFor("MISSING", "recordings/MISSING/video.mp4")));
        assertApiError("ACCESS_DENIED", 403, () -> service.create(
                principal(), "FOREIGN", IDEMPOTENCY_KEY,
                requestFor("FOREIGN", "recordings/FOREIGN/video.mp4")));
        verifyNoInteractions(storageVerifier, writer);
    }

    @Test
    void rejectsAlreadyRegisteredObjectBeforeStat() {
        when(recordingMapper.findByS3Key(OBJECT_KEY)).thenReturn(recording(99L, 80L));

        assertApiError("DUPLICATE_RESOURCE", 409,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));
        verifyNoInteractions(storageVerifier, writer);
    }

    @Test
    void classifiesStorageFailuresAndSizeBoundaries() {
        doThrow(new StorageObjectNotFoundException(null)).when(storageVerifier).stat(OBJECT_KEY);
        assertApiError("STORAGE_OBJECT_NOT_FOUND", 422,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));

        doThrow(new StorageObjectUnavailableException(null)).when(storageVerifier).stat(OBJECT_KEY);
        assertApiError("STORAGE_UNAVAILABLE", 503,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));

        doReturn(new StorageObject(0L, "video/mp4")).when(storageVerifier).stat(OBJECT_KEY);
        assertApiError("STORAGE_OBJECT_INVALID", 422,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));

        doReturn(new StorageObject(MAX_FILE_SIZE + 1, "video/mp4"))
                .when(storageVerifier).stat(OBJECT_KEY);
        assertApiError("FILE_TOO_LARGE", 413,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));

        doReturn(new StorageObject(MAX_FILE_SIZE, "video/mp4")).when(storageVerifier).stat(OBJECT_KEY);
        when(writer.create(eq(MEDIA_SERVER_ID), any(), eq(MAX_FILE_SIZE)))
                .thenReturn(recording(100L, MAX_FILE_SIZE));
        RecordingCreateResult atLimit = service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());
        assertEquals(MAX_FILE_SIZE, atLimit.recording().getFileSize());
    }

    @Test
    void usesDatabaseStateToResolveConcurrentConflicts() {
        when(storageVerifier.stat(OBJECT_KEY)).thenReturn(new StorageObject(80L, "video/mp4"));
        DuplicateKeyException duplicate = new DuplicateKeyException("concurrent");
        when(writer.create(eq(MEDIA_SERVER_ID), any(), eq(80L))).thenThrow(duplicate);
        NormalizedRecordingCreateRequest normalized = validator.validate(
                CAMERA_CODE, IDEMPOTENCY_KEY, request());
        when(recordingMapper.findRegistrationByKey(MEDIA_SERVER_ID, IDEMPOTENCY_KEY))
                .thenReturn(null)
                .thenReturn(new RecordingRegistrationResult(
                        MEDIA_SERVER_ID, IDEMPOTENCY_KEY, normalized.requestFingerprint(), recording(99L, 80L)));

        RecordingCreateResult replay = service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request());

        assertTrue(replay.duplicate());
    }

    @Test
    void doesNotMisclassifyUnknownDuplicateKeyFailure() {
        when(storageVerifier.stat(OBJECT_KEY)).thenReturn(new StorageObject(80L, "video/mp4"));
        DuplicateKeyException duplicate = new DuplicateKeyException("unexpected unique constraint");
        when(writer.create(eq(MEDIA_SERVER_ID), any(), eq(80L))).thenThrow(duplicate);

        DuplicateKeyException thrown = assertThrows(DuplicateKeyException.class,
                () -> service.create(principal(), CAMERA_CODE, IDEMPOTENCY_KEY, request()));

        assertSame(duplicate, thrown);
    }

    private MediaServerPrincipal principal() {
        return new MediaServerPrincipal(MEDIA_SERVER_ID, "media-1");
    }

    private RecordingCreateRequest request() {
        return requestFor(CAMERA_CODE, OBJECT_KEY);
    }

    private RecordingCreateRequest requestFor(String cameraCode, String objectKey) {
        return new RecordingCreateRequest(
                OffsetDateTime.parse("2026-07-20T10:00:00+09:00"),
                OffsetDateTime.parse("2026-07-20T10:01:00+09:00"),
                objectKey);
    }

    private Recording recording(Long id, Long fileSize) {
        return new Recording(
                id,
                CAMERA_ID,
                Instant.parse("2026-07-20T01:00:00Z"),
                Instant.parse("2026-07-20T01:01:00Z"),
                OBJECT_KEY,
                fileSize,
                Instant.parse("2026-07-20T01:01:01Z"));
    }

    private void assertApiError(String code, int status, Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals(code, exception.getCode());
        assertEquals(status, exception.getStatus().value());
    }
}
