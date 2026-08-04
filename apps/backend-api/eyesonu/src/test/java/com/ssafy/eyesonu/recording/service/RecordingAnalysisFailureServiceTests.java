package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyString;

import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisResultMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisFailureServiceTests {

    @Mock private AnalysisJobMapper jobMapper;
    @Mock private RecordingAnalysisResultMapper resultMapper;
    @Mock private AuditService auditService;
    @Mock private RecordingAnalysisJobClaimService claimService;

    private static final String CLAIM_TOKEN = "claim-token-5001";

    private RecordingAnalysisFailureService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisFailureService(
                jobMapper, resultMapper, auditService, claimService);
    }

    @Test
    void recordsFailureForRunningAttempt() {
        RecordingAnalysisFailureRequest request = request();
        AnalysisJob running = job("RUNNING", 0);
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(claimService.requireActiveWorkerJob(5001L, "worker-1", CLAIM_TOKEN)).thenReturn(running);
        when(claimService.hashClaimToken(CLAIM_TOKEN)).thenReturn("lease-hash");
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L, "worker-1", "lease-hash"))
                .thenReturn(running);
        when(jobMapper.markFailed(
                101L, 5001L, "worker-1", "lease-hash", "VIDEO_DECODE_FAILED: broken stream"))
                .thenReturn(1);

        var response = service.fail(5001L, request, "worker-1", CLAIM_TOKEN);

        assertEquals("FAILED", response.status());
        assertEquals(1, response.attempt());
        verify(resultMapper).insert(org.mockito.ArgumentMatchers.any(RecordingAnalysisResult.class));
    }

    @Test
    void acceptsIdenticalFailureRetry() {
        RecordingAnalysisFailureRequest request = request();
        RecordingAnalysisResult existing = new RecordingAnalysisResult();
        existing.setResultId(request.resultId());
        existing.setPayloadHash("dcf3ee10a655f03c2217484419389e4db967bb9b6642933ac652c6a6ca7ff4d9");
        existing.setStatus("FAILED");
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(job("FAILED", 0));
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(existing);

        var response = service.fail(5001L, request, "worker-1", CLAIM_TOKEN);

        assertTrue(response.duplicate());
        verify(jobMapper, never()).markFailed(
                org.mockito.ArgumentMatchers.any(), org.mockito.ArgumentMatchers.any(),
                org.mockito.ArgumentMatchers.any(), anyString(), anyString());
    }

    @Test
    void usesNextAttemptAfterAdminRetry() {
        RecordingAnalysisFailureRequest request = request();
        AnalysisJob running = job("RUNNING", 1);
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(running);
        when(resultMapper.findByJobIdAndAttempt(5001L, 2)).thenReturn(null);
        when(claimService.requireActiveWorkerJob(5001L, "worker-1", CLAIM_TOKEN)).thenReturn(running);
        when(claimService.hashClaimToken(CLAIM_TOKEN)).thenReturn("lease-hash");
        when(jobMapper.findRecordingAnalysisByIdForUpdate(5001L, "worker-1", "lease-hash"))
                .thenReturn(running);
        when(jobMapper.markFailed(
                101L, 5001L, "worker-1", "lease-hash", "VIDEO_DECODE_FAILED: broken stream"))
                .thenReturn(1);

        var response = service.fail(5001L, request, "worker-1", CLAIM_TOKEN);

        assertEquals(2, response.attempt());
    }

    @Test
    void rejectsFailureFromWorkerThatDidNotClaimJob() {
        when(jobMapper.findRecordingAnalysisById(5001L)).thenReturn(job("RUNNING", 0));
        when(resultMapper.findByJobIdAndAttempt(5001L, 1)).thenReturn(null);
        when(claimService.requireActiveWorkerJob(5001L, "worker-2", CLAIM_TOKEN))
                .thenThrow(new ApiException(org.springframework.http.HttpStatus.CONFLICT,
                        "WORKER_LEASE_CONFLICT", "Worker lease is not valid."));

        ApiException exception = assertThrows(ApiException.class, () ->
                service.fail(5001L, request(), "worker-2", CLAIM_TOKEN));

        assertEquals("WORKER_LEASE_CONFLICT", exception.getCode());
        verify(resultMapper, never()).insert(org.mockito.ArgumentMatchers.any());
    }

    private AnalysisJob job(String status, int retryCount) {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        job.setStatus(status);
        job.setRetryCount(retryCount);
        job.setClaimedBy("worker-1");
        return job;
    }

    private RecordingAnalysisFailureRequest request() {
        return new RecordingAnalysisFailureRequest(
                "failure-1", "VIDEO_DECODE_FAILED", "broken stream");
    }
}
