package com.ssafy.eyesonu.camera.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.CameraHeartbeatState;
import com.ssafy.eyesonu.camera.dto.device.CameraHeartbeatRequest;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class CameraHeartbeatServiceTests {

    private static final Long CAMERA_ID = 10L;
    private static final Long MEDIA_SERVER_ID = 20L;
    private static final String CAMERA_CODE = "CAM-001";
    private static final MediaServerPrincipal PRINCIPAL =
            new MediaServerPrincipal(MEDIA_SERVER_ID, "MS-001");

    private CameraMapper cameraMapper;
    private CameraHeartbeatService service;

    @BeforeEach
    void setUp() {
        cameraMapper = org.mockito.Mockito.mock(CameraMapper.class);
        service = new CameraHeartbeatService(cameraMapper);
    }

    @Test
    void acceptsOwnedHeartbeatAndUpdatesOccurredAtStatusAndHeartbeat() {
        Instant occurredAt = Instant.parse("2026-07-20T02:00:00Z");
        when(cameraMapper.findHeartbeatStateByCameraCodeForUpdate(CAMERA_CODE))
                .thenReturn(Optional.of(state("OFFLINE", null)));
        when(cameraMapper.updateHeartbeat(CAMERA_ID, "ONLINE", occurredAt)).thenReturn(1);

        service.receive(PRINCIPAL, CAMERA_CODE, request(occurredAt, "ONLINE", null));

        verify(cameraMapper).updateHeartbeat(CAMERA_ID, "ONLINE", occurredAt);
    }

    @Test
    void missingCameraReturnsResourceNotFound() {
        when(cameraMapper.findHeartbeatStateByCameraCodeForUpdate(CAMERA_CODE))
                .thenReturn(Optional.empty());

        assertApiError(
                "RESOURCE_NOT_FOUND", 404,
                () -> service.receive(PRINCIPAL, CAMERA_CODE, request(Instant.now(), "ONLINE", null)));
    }

    @Test
    void foreignCameraReturnsAccessDenied() {
        when(cameraMapper.findHeartbeatStateByCameraCodeForUpdate(CAMERA_CODE))
                .thenReturn(Optional.of(new CameraHeartbeatState(
                        CAMERA_ID, 999L, CAMERA_CODE, "OFFLINE", null)));

        assertApiError(
                "ACCESS_DENIED", 403,
                () -> service.receive(PRINCIPAL, CAMERA_CODE, request(Instant.now(), "ONLINE", null)));
        verify(cameraMapper, never()).updateHeartbeat(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void staleHeartbeatDoesNotOverwriteNewerState() {
        Instant latest = Instant.parse("2026-07-20T02:00:10Z");
        when(cameraMapper.findHeartbeatStateByCameraCodeForUpdate(CAMERA_CODE))
                .thenReturn(Optional.of(state("ONLINE", latest)));

        service.receive(
                PRINCIPAL,
                CAMERA_CODE,
                request(Instant.parse("2026-07-20T02:00:00Z"), "ERROR", "late packet"));

        verify(cameraMapper, never()).updateHeartbeat(org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void rejectsOfflineAsDeviceReportedStatusBecauseTimeoutOwnsOfflineTransition() {
        assertApiError(
                "VALIDATION_ERROR", 400,
                () -> service.receive(
                        PRINCIPAL,
                        CAMERA_CODE,
                        request(Instant.parse("2026-07-20T02:00:00Z"), "OFFLINE", null)));
        verify(cameraMapper, never()).findHeartbeatStateByCameraCodeForUpdate(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void marksOnlyTimedOutNonOfflineCamerasAndDoesNotRepeatChanges() {
        Instant now = Instant.parse("2026-07-20T02:01:00Z");
        Instant staleHeartbeat = Instant.parse("2026-07-20T02:00:20Z");
        CameraHeartbeatState candidate = state("ERROR", staleHeartbeat);
        when(cameraMapper.findOfflineCandidates(Instant.parse("2026-07-20T02:00:30Z")))
                .thenReturn(List.of(candidate));
        when(cameraMapper.markOffline(CAMERA_ID, staleHeartbeat, Instant.parse("2026-07-20T02:00:30Z")))
                .thenReturn(1);

        assertEquals(1, service.markOffline(now, Duration.ofSeconds(30)));

        verify(cameraMapper).markOffline(CAMERA_ID, staleHeartbeat, Instant.parse("2026-07-20T02:00:30Z"));
    }

    @Test
    void rejectsMalformedDirectServiceStatusAndMissingOccurredAt() {
        assertApiError(
                "VALIDATION_ERROR", 400,
                () -> service.receive(PRINCIPAL, CAMERA_CODE,
                        new CameraHeartbeatRequest(null, "ONLINE", null)));
        assertApiError(
                "VALIDATION_ERROR", 400,
                () -> service.receive(PRINCIPAL, CAMERA_CODE,
                        request(Instant.now(), "", null)));
    }

    private CameraHeartbeatState state(String status, Instant lastHeartbeat) {
        return new CameraHeartbeatState(CAMERA_ID, MEDIA_SERVER_ID, CAMERA_CODE, status, lastHeartbeat);
    }

    private CameraHeartbeatRequest request(Instant occurredAt, String status, String detail) {
        return new CameraHeartbeatRequest(
                OffsetDateTime.ofInstant(occurredAt, ZoneOffset.UTC), status, detail);
    }

    private void assertApiError(String code, int status, Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals(code, exception.getCode());
        assertEquals(status, exception.getStatus().value());
    }
}
