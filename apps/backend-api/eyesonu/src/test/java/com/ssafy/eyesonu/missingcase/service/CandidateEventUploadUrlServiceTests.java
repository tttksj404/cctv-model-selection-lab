package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateRequest;
import com.ssafy.eyesonu.missingcase.mapper.CandidateEventMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Duration;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class CandidateEventUploadUrlServiceTests {

    private static final long CASE_ID = 101L;
    private static final long CAMERA_ID = 11L;
    private static final long MEDIA_SERVER_ID = 2L;

    @Mock private CameraMapper cameraMapper;
    @Mock private CandidateEventMapper candidateEventMapper;
    @Mock private CaseQueryService caseQueryService;
    @Mock private StorageObjectUrlSigner urlSigner;

    private CandidateEventUploadUrlService service;

    @BeforeEach
    void setUp() {
        S3Properties properties = new S3Properties();
        properties.setPresignedUrlExpiry(Duration.ofMinutes(15));
        service = new CandidateEventUploadUrlService(
                cameraMapper, candidateEventMapper, caseQueryService,
                new CandidateEventObjectKeyFactory(), urlSigner, properties);
    }

    @Test
    void createsFrameAndCropUploadUrls() {
        prepareSearchableCamera();
        when(urlSigner.createPutUrl(anyString()))
                .thenAnswer(invocation -> "https://storage.example/upload/" + invocation.getArgument(0));

        var response = service.create(principal(), request("track-1"));

        assertEquals(900, response.expiresInSeconds());
        assertEquals("image/jpeg", response.frame().contentType());
        assertEquals(1, response.detections().size());
        assertEquals("track-1", response.detections().getFirst().trackId());
        assertEquals("image/png", response.detections().getFirst().contentType());
    }

    @Test
    void rejectsCameraOwnedByAnotherMediaServer() {
        when(cameraMapper.findByCameraCode("CAM-001"))
                .thenReturn(Optional.of(new Camera(CAMERA_ID, 99L, "CAM-001", "Front")));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(principal(), request("track-1")));

        assertEquals("ACCESS_DENIED", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    @Test
    void rejectsDuplicateTrackIds() {
        prepareSearchableCamera();

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(principal(), request("track-1", "track-1")));

        assertEquals("VALIDATION_ERROR", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    private void prepareSearchableCamera() {
        when(cameraMapper.findByCameraCode("CAM-001"))
                .thenReturn(Optional.of(new Camera(CAMERA_ID, MEDIA_SERVER_ID, "CAM-001", "Front")));
        MissingCaseRow row = new MissingCaseRow();
        row.setId(CASE_ID);
        row.setStatus(CaseStatus.SEARCHING);
        when(caseQueryService.require(CASE_ID)).thenReturn(row);
        when(candidateEventMapper.existsActiveCaseCamera(CASE_ID, CAMERA_ID)).thenReturn(true);
    }

    private MediaServerPrincipal principal() {
        return new MediaServerPrincipal(MEDIA_SERVER_ID, "media-01");
    }

    private CandidateEventUploadUrlCreateRequest request(String... trackIds) {
        List<CandidateEventUploadUrlCreateRequest.Detection> detections = List.of(trackIds).stream()
                .map(trackId -> new CandidateEventUploadUrlCreateRequest.Detection(trackId, "image/png"))
                .toList();
        return new CandidateEventUploadUrlCreateRequest(
                CASE_ID, "CAM-001", "event-1",
                new CandidateEventUploadUrlCreateRequest.Image("image/jpeg"), detections);
    }
}
