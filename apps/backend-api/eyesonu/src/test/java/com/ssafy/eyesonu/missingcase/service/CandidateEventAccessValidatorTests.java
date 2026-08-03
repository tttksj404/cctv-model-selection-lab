package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CandidateEventAccessValidatorTests {

    private static final long CASE_ID = 101L;
    private static final long CAMERA_ID = 11L;
    private static final long MEDIA_SERVER_ID = 2L;

    @Mock private CameraMapper cameraMapper;

    private CandidateEventObjectKeyFactory objectKeyFactory;
    private CandidateEventAccessValidator validator;

    @BeforeEach
    void setUp() {
        objectKeyFactory = new CandidateEventObjectKeyFactory();
        validator = new CandidateEventAccessValidator(cameraMapper, objectKeyFactory);
    }

    @Test
    void acceptsRealtimeKeysIssuedForAuthenticatedCamera() {
        Camera camera = camera();
        when(cameraMapper.findByCameraCode("CAM-001")).thenReturn(Optional.of(camera));

        Camera result = validator.validateRealtimeAccess(principal(), issuedRequest());

        assertEquals(camera, result);
    }

    @Test
    void rejectsRealtimeObjectKeyNotIssuedForAuthenticatedCamera() {
        when(cameraMapper.findByCameraCode("CAM-001")).thenReturn(Optional.of(camera()));

        ApiException exception = assertThrows(ApiException.class,
                () -> validator.validateRealtimeAccess(principal(), arbitraryRequest()));

        assertEquals("INVALID_UPLOAD_OBJECT_KEY", exception.getCode());
    }

    @Test
    void rejectsCameraOwnedByAnotherMediaServer() {
        when(cameraMapper.findByCameraCode("CAM-001"))
                .thenReturn(Optional.of(new Camera(CAMERA_ID, 99L, "CAM-001", "Front")));

        ApiException exception = assertThrows(ApiException.class,
                () -> validator.validateRealtimeAccess(principal(), issuedRequest()));

        assertEquals("ACCESS_DENIED", exception.getCode());
    }

    private Camera camera() {
        return new Camera(CAMERA_ID, MEDIA_SERVER_ID, "CAM-001", "Front");
    }

    private MediaServerPrincipal principal() {
        return new MediaServerPrincipal(MEDIA_SERVER_ID, "media-01");
    }

    private CandidateEventCreateRequest issuedRequest() {
        String frameKey = objectKeyFactory.frameKey(
                MEDIA_SERVER_ID, CAMERA_ID, CASE_ID, "event-1", "image/jpeg");
        String cropKey = objectKeyFactory.cropKey(
                MEDIA_SERVER_ID, CAMERA_ID, CASE_ID, "event-1", "track-1", "image/jpeg");
        return request(frameKey, cropKey);
    }

    private CandidateEventCreateRequest arbitraryRequest() {
        return request("frames/frame.jpg", "crops/crop.jpg");
    }

    private CandidateEventCreateRequest request(String frameKey, String cropKey) {
        return new CandidateEventCreateRequest(
                CASE_ID, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                frameKey, List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), cropKey,
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }
}
