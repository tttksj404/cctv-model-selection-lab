package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.mapper.CandidateEventMapper;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
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
class CandidateEventCommandServiceTests {

    private static final long CASE_ID = 101L;
    private static final long CAMERA_ID = 11L;
    private static final long MEDIA_SERVER_ID = 2L;

    @Mock private CameraMapper cameraMapper;
    @Mock private CandidateEventMapper mapper;
    @Mock private CaseQueryService caseQueryService;
    @Mock private StorageObjectVerifier storageObjectVerifier;

    private CandidateEventCommandService service;
    private CandidateEventObjectKeyFactory objectKeyFactory;
    private S3Properties s3Properties;

    @BeforeEach
    void setUp() {
        objectKeyFactory = new CandidateEventObjectKeyFactory();
        s3Properties = new S3Properties();
        s3Properties.setCandidateImageMaxFileSizeBytes(10 * 1024 * 1024);
        service = new CandidateEventCommandService(
                cameraMapper, mapper, caseQueryService, storageObjectVerifier, objectKeyFactory, s3Properties);
    }

    @Test
    void acceptsResultWhenExpectedCameraMatchesRequestCamera() {
        prepareValidRequest();
        when(mapper.insertEvent(any())).thenReturn(1);
        when(mapper.insertCandidate(any())).thenReturn(1);

        var response = service.create(
                principal(), request(), CAMERA_ID);

        assertEquals("event-1", response.eventId());
        assertEquals(1, response.detectionCount());
        verify(mapper).insertCandidate(any());
    }

    @Test
    void rejectsResultWhenExpectedCameraDoesNotMatchRequestCamera() {
        when(cameraMapper.findByCameraCode("CAM-001"))
                .thenReturn(Optional.of(new Camera(CAMERA_ID, MEDIA_SERVER_ID, "CAM-001", "Front")));

        ApiException exception = assertThrows(ApiException.class, () -> service.create(
                principal(), request(), 99L));

        assertEquals("CAMERA_MISMATCH", exception.getCode());
        verify(caseQueryService, never()).require(any());
        verify(mapper, never()).insertEvent(any());
    }

    @Test
    void acceptsRealtimeResultWithIssuedObjectKeys() {
        prepareValidRequest();
        when(mapper.insertEvent(any())).thenReturn(1);
        when(mapper.insertCandidate(any())).thenReturn(1);

        var response = service.create(principal(), realtimeRequest());

        assertEquals("event-1", response.eventId());
        verify(storageObjectVerifier).stat(realtimeRequest().frameObjectKey());
    }

    @Test
    void rejectsRealtimeResultWithUnissuedObjectKey() {
        prepareValidContext();

        ApiException exception = assertThrows(ApiException.class, () -> service.create(principal(), request()));

        assertEquals("INVALID_UPLOAD_OBJECT_KEY", exception.getCode());
        verify(storageObjectVerifier, never()).stat(anyString());
    }

    @Test
    void rejectsCandidateImageLargerThanConfiguredLimit() {
        prepareValidContext();
        when(storageObjectVerifier.stat(anyString()))
                .thenReturn(new StorageObject(10 * 1024 * 1024 + 1L, "image/jpeg"));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(principal(), request(), CAMERA_ID));

        assertEquals("STORAGE_OBJECT_TOO_LARGE", exception.getCode());
    }

    private void prepareValidRequest() {
        prepareValidContext();
        when(mapper.findEventByEventId(anyString())).thenReturn(null);
        when(storageObjectVerifier.stat(anyString())).thenReturn(new StorageObject(100L, "image/jpeg"));
    }

    private void prepareValidContext() {
        when(cameraMapper.findByCameraCode("CAM-001"))
                .thenReturn(Optional.of(new Camera(CAMERA_ID, MEDIA_SERVER_ID, "CAM-001", "Front")));
        when(caseQueryService.require(CASE_ID)).thenReturn(caseRow());
        when(mapper.existsActiveCaseCamera(CASE_ID, CAMERA_ID)).thenReturn(true);
    }

    private MissingCaseRow caseRow() {
        MissingCaseRow row = new MissingCaseRow();
        row.setId(CASE_ID);
        row.setStatus(CaseStatus.SEARCHING);
        return row;
    }

    private MediaServerPrincipal principal() {
        return new MediaServerPrincipal(MEDIA_SERVER_ID, "media-01");
    }

    private CandidateEventCreateRequest request() {
        return new CandidateEventCreateRequest(
                CASE_ID, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                "frames/frame.jpg", List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), "crops/crop.jpg",
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }

    private CandidateEventCreateRequest realtimeRequest() {
        String frameKey = objectKeyFactory.frameKey(MEDIA_SERVER_ID, CAMERA_ID, CASE_ID,
                "event-1", "image/jpeg");
        String cropKey = objectKeyFactory.cropKey(MEDIA_SERVER_ID, CAMERA_ID, CASE_ID,
                "event-1", "track-1", "image/jpeg");
        return new CandidateEventCreateRequest(
                CASE_ID, "CAM-001", "event-1", OffsetDateTime.parse("2026-08-02T10:00:00Z"),
                frameKey, List.of(new CandidateEventCreateRequest.Detection(
                        "track-1", new BigDecimal("0.91"), cropKey,
                        new CandidateEventCreateRequest.BoundingBox(1, 2, 30, 40))));
    }
}
