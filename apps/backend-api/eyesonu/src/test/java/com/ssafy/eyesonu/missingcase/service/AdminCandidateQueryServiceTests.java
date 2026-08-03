package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.missingcase.domain.AdminCandidateDetectionRow;
import com.ssafy.eyesonu.missingcase.domain.AdminCandidateRow;
import com.ssafy.eyesonu.missingcase.domain.CandidateSourceType;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateSearchCondition;
import com.ssafy.eyesonu.missingcase.mapper.AdminCandidateMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AdminCandidateQueryServiceTests {

    private final AdminCandidateMapper mapper = mock(AdminCandidateMapper.class);
    private final StorageObjectUrlSigner signer = mock(StorageObjectUrlSigner.class);
    private AdminCandidateQueryService service;

    @BeforeEach
    void setUp() {
        service = new AdminCandidateQueryService(mapper, signer);
    }

    @Test
    void returnsSignedUrlsInsteadOfObjectKeysInCandidateList() {
        AdminCandidateRow row = candidate();
        when(mapper.countCandidates(isNull(), isNull(), isNull(), isNull(), isNull(), isNull())).thenReturn(1L);
        when(mapper.findPage(isNull(), isNull(), isNull(), isNull(), isNull(), isNull(),
                any(), any(), anyInt(), anyLong())).thenReturn(List.of(row));
        stubSignedUrls();

        AdminCandidatePageResult result = service.findAll(
                new AdminCandidateSearchCondition(null, null, null, null, null, null,
                        0, 20, "lastDetectedAt,desc"));

        assertEquals("https://storage.example/crop", result.candidates().getFirst().cropUrl());
        assertEquals(CandidateSourceType.REALTIME, result.candidates().getFirst().sourceType());
        verify(signer, never()).createGetUrl("frames/frame.jpg");
    }

    @Test
    void signsCandidateAndDetectionUrlsInDetail() {
        AdminCandidateDetectionRow detection = new AdminCandidateDetectionRow();
        detection.setFrameObjectKey("frames/detection-frame.jpg");
        detection.setCropObjectKey("crops/detection-crop.jpg");
        when(mapper.findById(1L)).thenReturn(candidate());
        when(mapper.findDetections(1L)).thenReturn(List.of(detection));
        stubSignedUrls();

        AdminCandidateDetailResponse result = service.findById(1L);

        assertEquals("https://storage.example/frame", result.frameUrl());
        assertEquals("https://storage.example/crop", result.cropUrl());
        assertEquals("https://storage.example/detection-crop", result.detections().getFirst().cropUrl());
        verify(signer, never()).createGetUrl("frames/detection-frame.jpg");
        assertFalse(result.toString().contains("frames/frame.jpg"));
        assertFalse(result.toString().contains("crops/crop.jpg"));
        assertFalse(result.toString().contains("frames/detection-frame.jpg"));
        assertFalse(result.toString().contains("crops/detection-crop.jpg"));
    }

    private void stubSignedUrls() {
        when(signer.createGetUrl("frames/frame.jpg")).thenReturn("https://storage.example/frame");
        when(signer.createGetUrl("crops/crop.jpg")).thenReturn("https://storage.example/crop");
        when(signer.createGetUrl("crops/detection-crop.jpg"))
                .thenReturn("https://storage.example/detection-crop");
    }

    private AdminCandidateRow candidate() {
        AdminCandidateRow row = new AdminCandidateRow();
        row.setId(1L);
        row.setSourceType(CandidateSourceType.REALTIME);
        row.setFrameObjectKey("frames/frame.jpg");
        row.setCropObjectKey("crops/crop.jpg");
        return row;
    }
}
