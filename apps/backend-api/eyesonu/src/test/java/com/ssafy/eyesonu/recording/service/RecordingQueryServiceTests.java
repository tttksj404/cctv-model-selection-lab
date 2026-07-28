package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import com.ssafy.eyesonu.recording.domain.RecordingSortDirection;
import com.ssafy.eyesonu.recording.domain.RecordingSortField;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.Test;

class RecordingQueryServiceTests {

    private final RecordingMapper recordingMapper = mock(RecordingMapper.class);
    private final StorageObjectUrlSigner signer = mock(StorageObjectUrlSigner.class);
    private final RecordingQueryService service = new RecordingQueryService(
            recordingMapper, new RecordingRequestValidator(), signer);

    @Test
    void appliesNormalizedOverlapFilterPaginationAndSafeSortWithoutSigning() {
        OffsetDateTime from = OffsetDateTime.parse("2026-07-20T10:00:00+09:00");
        OffsetDateTime to = OffsetDateTime.parse("2026-07-20T11:00:00+09:00");
        Instant fromInstant = Instant.parse("2026-07-20T01:00:00Z");
        Instant toInstant = Instant.parse("2026-07-20T02:00:00Z");
        AdminRecordingRow row = row(12L);
        when(recordingMapper.countAdminRecordings(11L, fromInstant, toInstant)).thenReturn(5L);
        when(recordingMapper.findAdminPage(
                11L,
                fromInstant,
                toInstant,
                RecordingSortField.CREATED_AT,
                RecordingSortDirection.ASC,
                2,
                2L)).thenReturn(List.of(row));

        AdminRecordingPageResult result = service.findAll(
                new AdminRecordingSearchCondition(11L, from, to, 1, 2, "createdAt,asc"));

        assertEquals(1, result.page());
        assertEquals(2, result.size());
        assertEquals(5L, result.totalElements());
        assertEquals(3, result.totalPages());
        assertEquals("createdAt,asc", result.sort());
        assertEquals(12L, result.recordings().getFirst().id());
        assertEquals("CAM-001", result.recordings().getFirst().camera().cameraCode());
        verifyNoInteractions(signer);
    }

    @Test
    void emptyPageSkipsThePageQueryAndUsesDefaultSort() {
        when(recordingMapper.countAdminRecordings(null, null, null)).thenReturn(0L);

        AdminRecordingPageResult result = service.findAll(
                new AdminRecordingSearchCondition(null, null, null, 0, 20, null));

        assertEquals(List.of(), result.recordings());
        assertEquals(0, result.totalPages());
        assertEquals("startTime,desc", result.sort());
        verify(recordingMapper, never()).findAdminPage(
                any(), any(), any(), any(), any(), eq(20), eq(0L));
        verifyNoInteractions(signer);
    }

    @Test
    void rejectsInvalidBoundsPageSizeSortAndPrecision() {
        assertValidation(() -> service.findAll(new AdminRecordingSearchCondition(
                null,
                OffsetDateTime.parse("2026-07-20T01:00:00Z"),
                OffsetDateTime.parse("2026-07-20T01:00:00Z"),
                0,
                20,
                null)));
        assertValidation(() -> service.findAll(
                new AdminRecordingSearchCondition(null, null, null, -1, 20, null)));
        assertValidation(() -> service.findAll(
                new AdminRecordingSearchCondition(null, null, null, 0, 101, null)));
        assertValidation(() -> service.findAll(
                new AdminRecordingSearchCondition(null, null, null, 0, 20, "id,desc")));
        assertValidation(() -> service.findAll(new AdminRecordingSearchCondition(
                null,
                OffsetDateTime.parse("2026-07-20T01:00:00.1234567Z"),
                null,
                0,
                20,
                null)));
    }

    @Test
    void signsOnlyDetailAndMapsSigningFailure() {
        AdminRecordingRow row = row(12L);
        when(recordingMapper.findAdminDetail(12L)).thenReturn(row);
        when(signer.createGetUrl(row.getS3Key())).thenReturn("https://media.example.test/signed");

        AdminRecordingDetailResponse response = service.findById(12L);

        assertEquals("https://media.example.test/signed", response.videoUrl());
        assertEquals(11L, response.camera().id());
        verify(signer).createGetUrl(row.getS3Key());

        when(signer.createGetUrl(row.getS3Key()))
                .thenThrow(new StorageObjectUnavailableException(null));
        assertApiError("STORAGE_UNAVAILABLE", 503, () -> service.findById(12L));
    }

    @Test
    void missingDetailReturnsNotFoundWithoutSigning() {
        when(recordingMapper.findAdminDetail(404L)).thenReturn(null);

        assertApiError("RESOURCE_NOT_FOUND", 404, () -> service.findById(404L));

        verifyNoInteractions(signer);
    }

    private AdminRecordingRow row(Long id) {
        return new AdminRecordingRow(
                id,
                11L,
                "CAM-001",
                "Camera",
                Instant.parse("2026-07-20T01:00:00Z"),
                Instant.parse("2026-07-20T01:01:00Z"),
                "recordings/CAM-001/video.mp4",
                80L,
                Instant.parse("2026-07-20T01:01:01Z"));
    }

    private void assertValidation(Runnable action) {
        assertApiError("VALIDATION_ERROR", 400, action);
    }

    private void assertApiError(String code, int status, Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals(code, exception.getCode());
        assertEquals(status, exception.getStatus().value());
    }
}
