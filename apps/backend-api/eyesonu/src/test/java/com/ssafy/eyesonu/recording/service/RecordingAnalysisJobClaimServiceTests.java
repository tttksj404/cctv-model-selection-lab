package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobClaimServiceTests {

    private static final long JOB_ID = 5001L;

    @Mock
    private AnalysisJobMapper analysisJobMapper;

    private RecordingAnalysisJobClaimService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobClaimService(analysisJobMapper, 300);
    }

    @Test
    void claimsOnlyQueuedJobAndReloadsRunningSnapshot() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("RUNNING");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("backend-rabbit-consumer"), eq(300L)))
                .thenReturn(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isPresent());
        assertEquals("RUNNING", result.orElseThrow().getStatus());
        verify(analysisJobMapper).claimQueued(JOB_ID, "backend-rabbit-consumer", 300L);
        verify(analysisJobMapper).findRecordingAnalysisById(JOB_ID);
    }

    @Test
    void returnsEmptyWhenAnotherWorkerAlreadyClaimedJob() {
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("backend-rabbit-consumer"), eq(300L)))
                .thenReturn(0);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isEmpty());
        verify(analysisJobMapper, never()).findRecordingAnalysisById(JOB_ID);
    }

    @Test
    void returnsDuplicateWhenWorkerClaimsRunningJobAgain() {
        AnalysisJob job = runningJob();
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertTrue(result.duplicate());
        assertEquals("RUNNING", result.job().getStatus());
    }

    @Test
    void rejectsCompletedJobClaim() {
        AnalysisJob job = runningJob();
        job.setStatus("SUCCEEDED");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        ApiException exception = assertThrows(ApiException.class,
                () -> service.claimForWorker(JOB_ID, "worker-1"));

        assertEquals("JOB_NOT_RUNNABLE", exception.getCode());
    }

    @Test
    void reclaimsExpiredRunningJobForAnotherWorker() {
        AnalysisJob job = runningJob();
        job.setClaimedBy("worker-2");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), eq(300L)))
                .thenReturn(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals("RUNNING", result.job().getStatus());
        assertEquals("worker-2", result.job().getClaimedBy());
        assertTrue(!result.duplicate());
    }

    @Test
    void rejectsMissingWorkerIdentity() {
        ApiException exception = assertThrows(ApiException.class,
                () -> service.claimForWorker(JOB_ID, " "));

        assertEquals("AUTHENTICATION_REQUIRED", exception.getCode());
        verify(analysisJobMapper, never()).claimQueued(anyLong(), anyString(), anyLong());
    }

    private AnalysisJob runningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("RUNNING");
        return job;
    }
}
