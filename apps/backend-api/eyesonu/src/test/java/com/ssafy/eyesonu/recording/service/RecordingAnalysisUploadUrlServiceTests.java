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
    private static final String CLAIM_TOKEN = "claim-token-42";

    @Mock private StorageObjectUrlSigner urlSigner;
    @Mock private RecordingAnalysisJobClaimService claimService;

    private RecordingAnalysisUploadUrlService service;

    @BeforeEach
    void setUp() {
        MinioProperties properties = new MinioProperties();
        properties.setPresignedUrlExpiry(Duration.ofMinutes(15));
        service = new RecordingAnalysisUploadUrlService(
                new CandidateEventObjectKeyFactory(), urlSigner, properties, claimService);
    }

    @Test
    void createsFrameAndCropUrlsForClaimedAttempt() {
        AnalysisJob job = runningJob();
        job.setRetryCount(1);
        when(claimService.requireActiveWorkerJob(JOB_ID, WORKER_ID, CLAIM_TOKEN)).thenReturn(job);
        when(urlSigner.createPutUrl(anyString()))
                .thenAnswer(invocation -> "https://storage.example/" + invocation.getArgument(0));

        var response = service.create(JOB_ID, WORKER_ID, CLAIM_TOKEN, request("track-17"));

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
        when(claimService.requireActiveWorkerJob(JOB_ID, "another-worker", CLAIM_TOKEN))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.CONFLICT,
                        "WORKER_LEASE_CONFLICT", "Worker lease is not valid."));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, "another-worker", CLAIM_TOKEN, request("track-17")));

        assertEquals("WORKER_LEASE_CONFLICT", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    @Test
    void rejectsDuplicateTrackIds() {
        when(claimService.requireActiveWorkerJob(JOB_ID, WORKER_ID, CLAIM_TOKEN))
                .thenReturn(runningJob());

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, WORKER_ID, CLAIM_TOKEN, request("track-17", "track-17")));

        assertEquals("VALIDATION_ERROR", exception.getCode());
        verify(urlSigner, never()).createPutUrl(anyString());
    }

    @Test
    void mapsSignerFailureToStorageUnavailable() {
        when(claimService.requireActiveWorkerJob(JOB_ID, WORKER_ID, CLAIM_TOKEN))
                .thenReturn(runningJob());
        when(urlSigner.createPutUrl(anyString()))
                .thenThrow(new StorageObjectUnavailableException(new RuntimeException("down")));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.create(JOB_ID, WORKER_ID, CLAIM_TOKEN, request("track-17")));

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
