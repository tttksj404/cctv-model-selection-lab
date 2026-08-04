package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventCommandService;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisResultMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.mockito.ArgumentCaptor;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.transaction.support.TransactionCallback;
import org.springframework.transaction.support.TransactionTemplate;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisBatchResultServiceTests {

    @Mock private AnalysisJobMapper jobMapper;
    @Mock private RecordingAnalysisResultMapper resultMapper;
    @Mock private RecordingMapper recordingMapper;
    @Mock private CameraMapper cameraMapper;
    @Mock private CandidateEventCommandService candidateService;
    @Mock private AuditService auditService;
    @Mock private RecordingAnalysisResultStorageValidator resultStorageValidator;
    @Mock private RecordingAnalysisJobClaimService claimService;
    @Mock private TransactionTemplate transactionTemplate;

    private static final String CLAIM_TOKEN = "claim-token-5001";

    private RecordingAnalysisBatchResultService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisBatchResultService(
                jobMapper, resultMapper, recordingMapper, cameraMapper, candidateService,
                auditService, resultStorageValidator, claimService, transactionTemplate);
        org.mockito.Mockito.lenient().when(transactionTemplate.execute(any(TransactionCallback.class))).thenAnswer(invocation ->
                ((TransactionCallback<?>) invocation.getArgument(0)).doInTransaction(null));
    }

    @Test
    void completesSuccessfullyWithNoCandidates() {
        prepareRunningJob();
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of());

        var response = service.complete(5001L, request, "worker-1", CLAIM_TOKEN);

        assertEquals("SUCCEEDED", response.status());
        assertEquals(0, response.candidateCount());
        verify(candidateService, never()).createRecordingAnalysisBatch(any(), any(), any(), any(), any());
        verify(jobMapper).markSucceededForWorker(101L, 5001L, "worker-1", "lease-hash");
    }

    @Test
    void storesOneCandidatePerDeduplicatedTrack() {
        prepareRunningJob();
        when(candidateService.createRecordingAnalysisBatch(any(), any(), any(), any(), any()))
                .thenReturn(List.of(9001L, 9001L));
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of(candidate("track-1"), candidate("track-2")));

        var response = service.complete(5001L, request, "worker-1", CLAIM_TOKEN);

        assertEquals(List.of(9001L, 9001L), response.candidateIds());
        verify(candidateService)
                .createRecordingAnalysisBatch(any(), any(), any(), any(), any());
    }

    @Test
    void acceptsIdenticalResultRetryWithoutSavingCandidatesAgain() {
        AnalysisJob succeeded = job("SUCCEEDED");
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(succeeded);
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of());
        RecordingAnalysisResult existing = new RecordingAnalysisResult();
        existing.setJobId(5001L);
        existing.setAttempt(1);
        existing.setResultId("result-1");
        existing.setPayloadHash("deecc0c4cb65dfc4bc6f5adcdd1e37015a3f9c30e90e8984dfce5e1fc07ab06c");
        existing.setStatus("SUCCEEDED");
        existing.setCandidateCount(0);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(existing);

        var response = service.complete(5001L, request, "worker-1", CLAIM_TOKEN);

        assertTrue(response.duplicate());
        verify(jobMapper, never()).markSucceededForWorker(any(), any(), any(), any());
    }

    @Test
    void rejectsResultFromWorkerThatDidNotClaimJob() {
        AnalysisJob running = job("RUNNING");
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(claimService.requireActiveWorkerJob(5001L, "worker-2", CLAIM_TOKEN))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.CONFLICT,
                        "WORKER_LEASE_CONFLICT", "Worker lease is not valid."));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.complete(5001L, new RecordingAnalysisBatchResultRequest("result-1", List.of()),
                        "worker-2", CLAIM_TOKEN));

        assertEquals("WORKER_LEASE_CONFLICT", exception.getCode());
        verify(resultStorageValidator, never()).verify(any(), any());
        verify(jobMapper, never()).markSucceededForWorker(any(), any(), any(), any());
    }

    @Test
    void treatsEquivalentBigDecimalScalesAsTheSameRetryPayload() {
        prepareRunningJob();
        when(candidateService.createRecordingAnalysisBatch(any(), any(), any(), any(), any()))
                .thenReturn(List.of(9001L));
        RecordingAnalysisBatchResultRequest firstRequest = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of(candidateWithSimilarity("track-1", "0.90")));

        service.complete(5001L, firstRequest, "worker-1", CLAIM_TOKEN);

        ArgumentCaptor<RecordingAnalysisResult> resultCaptor = ArgumentCaptor.forClass(
                RecordingAnalysisResult.class);
        verify(resultMapper).insert(resultCaptor.capture());
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(job("SUCCEEDED"));
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(resultCaptor.getValue());
        RecordingAnalysisBatchResultRequest retryRequest = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of(candidateWithSimilarity("track-1", "0.9")));

        var response = service.complete(5001L, retryRequest, "worker-1", CLAIM_TOKEN);

        assertTrue(response.duplicate());
    }

    private void prepareRunningJob() {
        AnalysisJob running = job("RUNNING");
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(claimService.requireActiveWorkerJob(5001L, "worker-1", CLAIM_TOKEN)).thenReturn(running);
        when(claimService.hashClaimToken(CLAIM_TOKEN)).thenReturn("lease-hash");
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L, "worker-1", "lease-hash"))
                .thenReturn(running);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(recordingMapper.findById(3001L)).thenReturn(new Recording(
                3001L, 11L, null, null, "recordings/CAM-001/video.mp4", 100L, null));
        when(cameraMapper.findById(11L)).thenReturn(Optional.of(
                new Camera(11L, 2L, "CAM-001", "Front")));
        when(jobMapper.markSucceededForWorker(101L, 5001L, "worker-1", "lease-hash"))
                .thenReturn(1);
    }

    private AnalysisJob job(String status) {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        job.setRecordingId(3001L);
        job.setStatus(status);
        job.setClaimedBy("worker-1");
        return job;
    }

    private RecordingAnalysisBatchResultRequest.Candidate candidate(String trackId) {
        return candidateWithSimilarity(trackId, "0.91");
    }

    private RecordingAnalysisBatchResultRequest.Candidate candidateWithSimilarity(
            String trackId, String similarity) {
        return new RecordingAnalysisBatchResultRequest.Candidate(
                trackId, OffsetDateTime.parse("2026-08-03T10:00:00Z"), new BigDecimal(similarity),
                "analysis/analysis-5001/attempt-1/frames/" + trackId + ".jpg",
                "analysis/analysis-5001/attempt-1/crops/" + trackId + ".jpg",
                new RecordingAnalysisBatchResultRequest.BoundingBox(1, 2, 30, 40));
    }
}
