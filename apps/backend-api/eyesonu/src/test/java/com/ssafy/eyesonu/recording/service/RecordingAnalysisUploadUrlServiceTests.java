package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.time.Duration;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisUploadUrlServiceTests {

    private static final long JOB_ID = 42L;
    private static final String WORKER_ID = "recording-ai-worker";

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private StorageObjectUrlSigner urlSigner;

    private RecordingAnalysisUploadUrlService service;

    @BeforeEach
    void setUp() {
        MinioProperties properties = new MinioProperties();
        properties.setPresignedUrlExpiry(Duration.ofMinutes(15));
        service = new RecordingAnalysisUploadUrlService(
                analysisJobMapper, new CandidateEventObjectKeyFactory(), urlSigner, properties);
    }

    @Test
    void createsFrameAndCropUrlsForClaimedAttempt() {
        AnalysisJob job = runningJob();
        job.setRetryCount(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);
        when(urlSigner.createPutUrl(anyString()))
                .thenAnswer(invocation -> "https://storage.example/" + invocation.getArgument(0));

        var response = service.create(JOB_ID, WORKER_ID, request("track-17"));

        assertEquals(2, response.attempt());
        assertEquals(900, response.expiresInSeconds());
        assertEquals(1, response.candidates().size());
        assertEquals("track-17", response.candidates().getFirst().trackId());
        assertEquals("image/jpeg", response.candidates().getFirst().frame().contentType());
        assertEquals("image/png", response.candidates().getFirst().crop().contentType());
        verify(urlSigner).createPutUrl(response.candidates().getFirst().frame().objectKey());
        verify(urlSigner).createPutUrl(response.candidates().getFirst().crop().objectKey());
    }

    @Test
    void rejectsUploadUrlRequestFromAnotherWorker() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(runningJob());

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, "another-worker", request("track-17")));

        assertEquals("JOB_NOT_CLAIMED", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    @Test
    void rejectsDuplicateTrackIds() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(runningJob());

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, WORKER_ID, request("track-17", "track-17")));

        assertEquals("VALIDATION_ERROR", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    @Test
    void mapsSignerFailureToStorageUnavailable() {
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(runningJob());
        when(urlSigner.createPutUrl(anyString()))
                .thenThrow(new StorageObjectUnavailableException(new RuntimeException("down")));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, WORKER_ID, request("track-17")));

        assertEquals("STORAGE_UNAVAILABLE", exception.getCode());
    }

    private AnalysisJob runningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setStatus("RUNNING");
        job.setClaimedBy(WORKER_ID);
        job.setRetryCount(0);
        return job;
    }

    private RecordingAnalysisUploadUrlCreateRequest request(String... trackIds) {
        List<RecordingAnalysisUploadUrlCreateRequest.Candidate> candidates = List.of(trackIds).stream()
                .map(trackId -> new RecordingAnalysisUploadUrlCreateRequest.Candidate(
                        trackId, "image/jpeg", "image/png"))
                .toList();
        return new RecordingAnalysisUploadUrlCreateRequest(candidates);
    }
}
