package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertSame;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistration;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.lang.reflect.Method;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;
import org.springframework.transaction.annotation.Transactional;

class RecordingRegistrationWriterTests {

    private final CameraMapper cameraMapper = mock(CameraMapper.class);
    private final RecordingMapper recordingMapper = mock(RecordingMapper.class);
    private final RecordingRegistrationWriter writer =
            new RecordingRegistrationWriter(cameraMapper, recordingMapper);

    @Test
    void locksAndRechecksOwnershipThenAtomicallyWritesAndReloads() throws Exception {
        NormalizedRecordingCreateRequest request = request();
        Camera camera = new Camera(11L, 7L, request.cameraCode(), "Camera");
        Recording persisted = new Recording(
                99L, 11L, request.startTime(), request.endTime(), request.objectKey(), 80L,
                Instant.parse("2026-07-20T01:01:01Z"));
        when(cameraMapper.findByCameraCodeForUpdate(request.cameraCode())).thenReturn(Optional.of(camera));
        when(recordingMapper.insert(any(Recording.class))).thenAnswer(invocation -> {
            invocation.getArgument(0, Recording.class).setId(99L);
            return 1;
        });
        when(recordingMapper.insertRegistration(any(RecordingRegistration.class))).thenReturn(1);
        when(recordingMapper.findById(99L)).thenReturn(persisted);

        Recording result = writer.create(7L, request, 80L);

        assertSame(persisted, result);
        verify(cameraMapper).findByCameraCodeForUpdate(request.cameraCode());
        ArgumentCaptor<RecordingRegistration> registration =
                ArgumentCaptor.forClass(RecordingRegistration.class);
        verify(recordingMapper).insertRegistration(registration.capture());
        assertEquals(7L, registration.getValue().getMediaServerId());
        assertEquals(99L, registration.getValue().getRecordingId());
        Method method = RecordingRegistrationWriter.class.getMethod(
                "create", long.class, NormalizedRecordingCreateRequest.class, long.class);
        assertTrue(method.isAnnotationPresent(Transactional.class));
    }

    @Test
    void blocksOwnershipChangeDetectedImmediatelyBeforeInsert() {
        when(cameraMapper.findByCameraCodeForUpdate(request().cameraCode())).thenReturn(Optional.of(
                new Camera(11L, 999L, request().cameraCode(), "Camera")));

        ApiException exception = assertThrows(ApiException.class, () -> writer.create(7L, request(), 80L));

        assertEquals("ACCESS_DENIED", exception.getCode());
        assertEquals(403, exception.getStatus().value());
    }

    private NormalizedRecordingCreateRequest request() {
        return new NormalizedRecordingCreateRequest(
                "CAM-001",
                "550e8400-e29b-41d4-a716-446655440000",
                Instant.parse("2026-07-20T01:00:00Z"),
                Instant.parse("2026-07-20T01:01:00Z"),
                "recordings/CAM-001/video.mp4",
                "a".repeat(64));
    }
}
