package com.ssafy.eyesonu.camera.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import com.ssafy.eyesonu.camera.domain.CameraStreamUrlRow;
import com.ssafy.eyesonu.camera.domain.CameraUpdateCommand;
import com.ssafy.eyesonu.camera.dto.CameraCreateRequest;
import com.ssafy.eyesonu.camera.dto.CameraNamePatchRequest;
import com.ssafy.eyesonu.camera.dto.CameraPutRequest;
import com.ssafy.eyesonu.camera.dto.CameraStreamUrlResponse;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.mediaserver.domain.MediaServer;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.dao.DuplicateKeyException;

class CameraServiceTests {

    private static final Long ADMIN_ID = 1L;
    private static final Long CAMERA_ID = 10L;
    private static final Long MEDIA_SERVER_ID = 20L;

    private CameraMapper cameraMapper;
    private MediaServerMapper mediaServerMapper;
    private AuditService auditService;
    private CameraService cameraService;

    @BeforeEach
    void setUp() {
        cameraMapper = mock(CameraMapper.class);
        mediaServerMapper = mock(MediaServerMapper.class);
        auditService = mock(AuditService.class);
        cameraService = new CameraService(cameraMapper, mediaServerMapper, auditService);
        when(mediaServerMapper.findById(MEDIA_SERVER_ID)).thenReturn(Optional.of(mediaServer()));
    }

    @Test
    void validatesPageStatusAndSortContract() {
        assertApiError("VALIDATION_ERROR", 400,
                () -> cameraService.findAdminPage(null, null, -1, 20, "createdAt,desc"));
        assertApiError("VALIDATION_ERROR", 400,
                () -> cameraService.findAdminPage(null, null, 0, 101, "createdAt,desc"));
        assertApiError("VALIDATION_ERROR", 400,
                () -> cameraService.findAdminPage("ACTIVE", null, 0, 20, "createdAt,desc"));
        assertApiError("VALIDATION_ERROR", 400,
                () -> cameraService.findAdminPage(null, null, 0, 20, "id,desc"));
        verifyNoInteractions(cameraMapper);
    }

    @Test
    void listUsesDefaultPaginationAndSafeSortMapping() {
        when(cameraMapper.countAdminCameras("OFFLINE", "park")).thenReturn(21L);
        when(cameraMapper.findAdminPage("OFFLINE", "park", "created_at", "DESC", 20, 20))
                .thenReturn(List.of(row("rtsp://internal")));

        CameraPageResult result = cameraService.findAdminPage(
                "offline", " park ", 1, 20, "createdAt,desc");

        assertEquals(1, result.page());
        assertEquals(20, result.size());
        assertEquals(21L, result.totalElements());
        assertEquals(2, result.totalPages());
        assertEquals("createdAt,desc", result.sort());
        assertEquals(1, result.cameras().size());
    }

    @Test
    void findsStreamUrlFromCameraRecord() {
        when(cameraMapper.findStreamUrlById(CAMERA_ID))
                .thenReturn(new CameraStreamUrlRow(CAMERA_ID, "rtsp://internal/stream"));

        CameraStreamUrlResponse result = cameraService.findStreamUrlById(CAMERA_ID);

        assertEquals("rtsp://internal/stream", result.streamUrl());
        verify(cameraMapper).findStreamUrlById(CAMERA_ID);
    }

    @Test
    void missingCameraPreventsStreamUrlLookup() {
        when(cameraMapper.findStreamUrlById(CAMERA_ID)).thenReturn(null);

        assertApiError("RESOURCE_NOT_FOUND", 404,
                () -> cameraService.findStreamUrlById(CAMERA_ID));
    }

    @Test
    void unconfiguredStreamUrlIsReportedSeparatelyFromMissingCamera() {
        when(cameraMapper.findStreamUrlById(CAMERA_ID))
                .thenReturn(new CameraStreamUrlRow(CAMERA_ID, null));

        assertApiError("STREAM_URL_NOT_CONFIGURED", 404,
                () -> cameraService.findStreamUrlById(CAMERA_ID));
    }

    @Test
    void missingMediaServerPreventsRegistration() {
        when(mediaServerMapper.findById(999L)).thenReturn(Optional.empty());

        assertApiError("RESOURCE_NOT_FOUND", 404,
                () -> cameraService.create(ADMIN_ID, createRequest(999L, "CAM-999")));
        verifyNoInteractions(auditService);
    }

    @Test
    void duplicateCameraCodeMapsToConflict() {
        when(cameraMapper.insert(any())).thenThrow(new DuplicateKeyException("duplicate"));

        assertApiError("DUPLICATE_RESOURCE", 409,
                () -> cameraService.create(ADMIN_ID, createRequest(MEDIA_SERVER_ID, "CAM-001")));
        verifyNoInteractions(auditService);
    }

    @Test
    void createsOfflineCameraAndDoesNotAuditRtspUrl() {
        CameraManagementRow created = row("rtsp://secret.example/stream");
        when(cameraMapper.insert(any())).thenAnswer(invocation -> {
            invocation.<com.ssafy.eyesonu.camera.domain.CameraCreateCommand>getArgument(0).setId(CAMERA_ID);
            return 1;
        });
        when(cameraMapper.findAdminById(CAMERA_ID)).thenReturn(created);

        cameraService.create(ADMIN_ID, createRequest(MEDIA_SERVER_ID, "CAM-001"));

        verify(cameraMapper).insert(any());
        verify(auditService).recordRequired(
                eq("CAMERA_CREATED"), eq(ADMIN_ID), eq(null), eq("CAMERA"), eq(CAMERA_ID),
                eq(Map.of(
                        "cameraCode", "CAM-001",
                        "cameraName", "Front Gate",
                        "mediaServerId", MEDIA_SERVER_ID,
                        "status", "OFFLINE")));
    }

    @Test
    void patchLocksCameraAndUpdatesOnlyName() {
        CameraManagementRow before = row("rtsp://internal");
        CameraManagementRow after = new CameraManagementRow(
                CAMERA_ID, MEDIA_SERVER_ID, "MS-001", "Media Server", "CAM-001", "Renamed",
                before.latitude(), before.longitude(), before.address(), before.rtspUrl(),
                before.status(), before.lastHeartbeat(), before.createdAt(), before.updatedAt());
        when(cameraMapper.findAdminByIdForUpdate(CAMERA_ID)).thenReturn(before);
        when(cameraMapper.updateName(CAMERA_ID, "Renamed")).thenReturn(1);
        when(cameraMapper.findAdminById(CAMERA_ID)).thenReturn(after);

        cameraService.patchName(ADMIN_ID, CAMERA_ID, new CameraNamePatchRequest(" Renamed "));

        verify(cameraMapper).findAdminByIdForUpdate(CAMERA_ID);
        verify(cameraMapper).updateName(CAMERA_ID, "Renamed");
        verify(auditService).recordRequired(
                eq("CAMERA_NAME_UPDATED"), eq(ADMIN_ID), eq(null), eq("CAMERA"), eq(CAMERA_ID),
                eq(Map.of("beforeName", "Front Gate", "afterName", "Renamed")));
    }

    @Test
    void putPreservesCameraCodeStatusAndHeartbeat() {
        CameraManagementRow before = row("rtsp://old");
        CameraManagementRow after = new CameraManagementRow(
                CAMERA_ID, 21L, "MS-002", "New Media Server", "CAM-001", "Updated",
                new BigDecimal("37.5000000"), new BigDecimal("127.0000000"), "New address",
                "rtsp://new", "ERROR", before.lastHeartbeat(), before.createdAt(), before.updatedAt());
        when(cameraMapper.findAdminByIdForUpdate(CAMERA_ID)).thenReturn(before);
        when(mediaServerMapper.findById(21L)).thenReturn(Optional.of(
                new MediaServer(21L, "MS-002", "New Media Server", "device-key-2", "hash-2", "DISABLED")));
        when(cameraMapper.updateDetails(any(CameraUpdateCommand.class))).thenReturn(1);
        when(cameraMapper.findAdminById(CAMERA_ID)).thenReturn(after);

        cameraService.replace(ADMIN_ID, CAMERA_ID, new CameraPutRequest(
                21L, "Updated", new BigDecimal("37.5000000"), new BigDecimal("127.0000000"),
                "New address", "rtsp://new"));

        verify(cameraMapper).updateDetails(new CameraUpdateCommand(
                CAMERA_ID, 21L, "Updated", new BigDecimal("37.5000000"),
                new BigDecimal("127.0000000"), "New address", "rtsp://new"));
        assertEquals("CAM-001", after.cameraCode());
        assertEquals("ERROR", after.status());
        assertEquals(before.lastHeartbeat(), after.lastHeartbeat());
    }

    @Test
    void requiredAuditFailurePropagatesForTransactionRollback() {
        CameraManagementRow before = row("rtsp://old");
        when(cameraMapper.findAdminByIdForUpdate(CAMERA_ID)).thenReturn(before);
        when(cameraMapper.updateName(CAMERA_ID, "Renamed")).thenReturn(1);
        when(cameraMapper.findAdminById(CAMERA_ID)).thenReturn(row("rtsp://old"));
        doThrow(new DataAccessResourceFailureException("audit unavailable"))
                .when(auditService)
                .recordRequired(any(), any(), any(), any(), any(), any());

        assertThrows(DataAccessResourceFailureException.class,
                () -> cameraService.patchName(ADMIN_ID, CAMERA_ID, new CameraNamePatchRequest("Renamed")));
    }

    private CameraCreateRequest createRequest(Long mediaServerId, String cameraCode) {
        return new CameraCreateRequest(
                mediaServerId,
                cameraCode,
                "Front Gate",
                new BigDecimal("37.5000000"),
                new BigDecimal("127.0000000"),
                "Main address",
                "rtsp://secret.example/stream");
    }

    private MediaServer mediaServer() {
        return new MediaServer(
                MEDIA_SERVER_ID, "MS-001", "Media Server", "device-key", "hash", "DISABLED");
    }

    private CameraManagementRow row(String rtspUrl) {
        return new CameraManagementRow(
                CAMERA_ID,
                MEDIA_SERVER_ID,
                "MS-001",
                "Media Server",
                "CAM-001",
                "Front Gate",
                new BigDecimal("37.5000000"),
                new BigDecimal("127.0000000"),
                "Main address",
                rtspUrl,
                "OFFLINE",
                Instant.parse("2026-07-29T00:00:00Z"),
                Instant.parse("2026-07-28T00:00:00Z"),
                Instant.parse("2026-07-28T00:00:00Z"));
    }

    private void assertApiError(String code, int status, Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals(code, exception.getCode());
        assertEquals(status, exception.getStatus().value());
    }
}
