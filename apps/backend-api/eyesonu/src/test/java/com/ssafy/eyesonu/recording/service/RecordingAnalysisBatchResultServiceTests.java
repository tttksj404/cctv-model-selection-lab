package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
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
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.time.OffsetDateTime;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
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
    @Mock private TransactionTemplate transactionTemplate;

    private RecordingAnalysisBatchResultService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisBatchResultService(
                jobMapper, resultMapper, recordingMapper, cameraMapper, candidateService,
                auditService, resultStorageValidator, transactionTemplate);
        org.mockito.Mockito.lenient().when(transactionTemplate.execute(any(TransactionCallback.class))).thenAnswer(invocation ->
                ((TransactionCallback<?>) invocation.getArgument(0)).doInTransaction(null));
    }

    @Test
    void completesSuccessfullyWithNoCandidates() {
        prepareRunningJob();
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of());

        var response = service.complete(5001L, request, "worker-1");

        assertEquals("SUCCEEDED", response.status());
        assertEquals(0, response.candidateCount());
        verify(candidateService, never()).createRecordingAnalysisBatch(any(), any(), any(), any(), any());
        verify(jobMapper).markSucceeded(101L, 5001L);
    }

    @Test
    void storesOneCandidatePerDeduplicatedTrack() {
        prepareRunningJob();
        when(candidateService.createRecordingAnalysisBatch(any(), any(), any(), any(), any()))
                .thenReturn(List.of(9001L, 9001L));
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "result-1", List.of(candidate("track-1"), candidate("track-2")));

        var response = service.complete(5001L, request, "worker-1");

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
        existing.setPayloadHash(hash(request));
        existing.setStatus("SUCCEEDED");
        existing.setCandidateCount(0);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(existing);

        var response = service.complete(5001L, request, "worker-1");

        assertTrue(response.duplicate());
        verify(jobMapper, never()).markSucceeded(any(), any());
    }

    @Test
    void completesLeaseBoundAiWorkerResultAndProjectsCandidates() {
        AnalysisJob running = job("RUNNING");
        running.setClaimedBy("notebook-1");
        running.setLeaseTokenHash("lease-hash");
        running.setClaimExpiresAt(Instant.now().plusSeconds(60));
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L)).thenReturn(running);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(recordingMapper.findById(3001L)).thenReturn(new Recording(
                3001L, 11L, null, null, "recordings/CAM-001/video.mp4", 100L, null));
        when(cameraMapper.findById(11L)).thenReturn(Optional.of(
                new Camera(11L, 2L, "CAM-001", "Front")));
        when(candidateService.createRecordingAnalysisBatch(any(), any(), any(), any(), any()))
                .thenReturn(List.of(9001L));
        when(jobMapper.complete(5001L, "notebook-1", "lease-hash", "hybrid-v1", "{}", "result-hash"))
                .thenReturn(1);
        RecordingAnalysisBatchResultRequest request = new RecordingAnalysisBatchResultRequest(
                "ai-worker-5001-attempt-1-result-hash", List.of(candidate("track-1")));

        var response = service.completeFromAiWorker(
                5001L,
                request,
                "notebook-1",
                "lease-hash",
                "hybrid-v1",
                "{}",
                "result-hash");

        assertEquals("SUCCEEDED", response.status());
        assertEquals(List.of(9001L), response.candidateIds());
        verify(resultStorageValidator).verify(running, request);
        verify(jobMapper).complete(
                5001L, "notebook-1", "lease-hash", "hybrid-v1", "{}", "result-hash");
    }

    private void prepareRunningJob() {
        AnalysisJob running = job("RUNNING");
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L)).thenReturn(running);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(recordingMapper.findById(3001L)).thenReturn(new Recording(
                3001L, 11L, null, null, "recordings/CAM-001/video.mp4", 100L, null));
        when(cameraMapper.findById(11L)).thenReturn(Optional.of(
                new Camera(11L, 2L, "CAM-001", "Front")));
        when(jobMapper.markSucceeded(101L, 5001L)).thenReturn(1);
    }

    private AnalysisJob job(String status) {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        job.setRecordingId(3001L);
        job.setStatus(status);
        return job;
    }

    private RecordingAnalysisBatchResultRequest.Candidate candidate(String trackId) {
        return new RecordingAnalysisBatchResultRequest.Candidate(
                trackId, OffsetDateTime.parse("2026-08-03T10:00:00Z"), new BigDecimal("0.91"),
                "analysis/analysis-5001/attempt-1/frames/" + trackId + ".jpg",
                "analysis/analysis-5001/attempt-1/crops/" + trackId + ".jpg",
                new RecordingAnalysisBatchResultRequest.BoundingBox(1, 2, 30, 40));
    }

    private String hash(RecordingAnalysisBatchResultRequest request) {
        try {
            return HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256")
                    .digest(request.toString().getBytes(StandardCharsets.UTF_8)));
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }
}
