package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.missingcase.service.CandidateEventStorageValidator;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisResultStorageValidatorTests {

    @Mock private CandidateEventStorageValidator storageValidator;
    private RecordingAnalysisResultStorageValidator validator;

    @BeforeEach
    void setUp() {
        validator = new RecordingAnalysisResultStorageValidator(
                new CandidateEventObjectKeyFactory(), storageValidator);
    }

    @Test
    void verifiesObjectsUnderCurrentJobAttemptPrefix() {
        AnalysisJob job = job();
        CandidateEventObjectKeyFactory keyFactory = new CandidateEventObjectKeyFactory();
        RecordingAnalysisBatchResultRequest request = request(
                keyFactory.analysisFrameKey(5001L, 2, "track-1", "image/jpeg"),
                keyFactory.analysisCropKey(5001L, 2, "track-1", "image/jpeg"));

        validator.verify(job, request);

        verify(storageValidator).verify(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void rejectsObjectsFromAnotherJobBeforeStorageLookup() {
        CandidateEventObjectKeyFactory keyFactory = new CandidateEventObjectKeyFactory();
        RecordingAnalysisBatchResultRequest request = request(
                keyFactory.analysisFrameKey(9999L, 2, "track-1", "image/jpeg"),
                keyFactory.analysisCropKey(9999L, 2, "track-1", "image/jpeg"));

        ApiException exception = assertThrows(ApiException.class, () -> validator.verify(job(), request));

        assertEquals("INVALID_UPLOAD_OBJECT_KEY", exception.getCode());
        verify(storageValidator, never()).verify(org.mockito.ArgumentMatchers.any());
    }

    @Test
    void rejectsArbitraryKeyUnderCurrentJobAttemptPrefix() {
        RecordingAnalysisBatchResultRequest request = request(
                "analysis/analysis-5001/attempt-2/frames/not-issued.jpg",
                "analysis/analysis-5001/attempt-2/crops/not-issued.jpg");

        ApiException exception = assertThrows(ApiException.class, () -> validator.verify(job(), request));

        assertEquals("INVALID_UPLOAD_OBJECT_KEY", exception.getCode());
        verify(storageValidator, never()).verify(org.mockito.ArgumentMatchers.any());
    }

    private AnalysisJob job() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        job.setRetryCount(1);
        return job;
    }

    private RecordingAnalysisBatchResultRequest request(String frameKey, String cropKey) {
        return new RecordingAnalysisBatchResultRequest("result-1", List.of(
                new RecordingAnalysisBatchResultRequest.Candidate(
                        "track-1", OffsetDateTime.parse("2026-08-03T10:00:00Z"),
                        new BigDecimal("0.91"), frameKey, cropKey,
                        new RecordingAnalysisBatchResultRequest.BoundingBox(1, 2, 30, 40))));
    }
}
