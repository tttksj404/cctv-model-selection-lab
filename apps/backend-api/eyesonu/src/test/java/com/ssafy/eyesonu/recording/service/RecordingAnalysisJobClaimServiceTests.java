package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.util.Optional;
import java.time.Instant;
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
        when(analysisJobMapper.claimQueued(
                eq(JOB_ID), eq("backend-rabbit-consumer"), anyString(), eq(300L)))
                .thenReturn(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isPresent());
        assertEquals("RUNNING", result.orElseThrow().getStatus());
        verify(analysisJobMapper).claimQueued(
                eq(JOB_ID), eq("backend-rabbit-consumer"), anyString(), eq(300L));
        verify(analysisJobMapper).findRecordingAnalysisById(JOB_ID);
    }

    @Test
    void returnsEmptyWhenAnotherWorkerAlreadyClaimedJob() {
        when(analysisJobMapper.claimQueued(
                eq(JOB_ID), eq("backend-rabbit-consumer"), anyString(), eq(300L)))
                .thenReturn(0);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isEmpty());
        verify(analysisJobMapper, never()).findRecordingAnalysisById(JOB_ID);
    }

    @Test
    void returnsLeaseHeldByOtherWhenAnotherWorkerHasAnActiveLease() {
        AnalysisJob job = runningJob();
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals(RecordingAnalysisClaimDisposition.LEASE_HELD_BY_OTHER, result.disposition());
        assertEquals("RUNNING", result.job().getStatus());
        assertEquals(null, result.leaseToken());
    }

    @Test
    void returnsLeaseHeldBySelfForAStaleDeliveryToTheSameWorker() {
        AnalysisJob job = runningJob();
        job.setClaimedBy("worker-1");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals(RecordingAnalysisClaimDisposition.LEASE_HELD_BY_SELF, result.disposition());
        assertEquals(null, result.leaseToken());
    }

    @Test
    void returnsTheNextClaimableTimeForLegacyRunningJobWithoutLeaseExpiry() {
        Instant startedAt = Instant.now().minusSeconds(20);
        AnalysisJob job = runningJob();
        job.setStartedAt(startedAt);
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals(RecordingAnalysisClaimDisposition.LEASE_HELD_BY_OTHER, result.disposition());
        assertEquals(startedAt.plusSeconds(300), result.job().getClaimExpiresAt());
    }

    @Test
    void returnsTerminalDispositionForCompletedJobClaim() {
        AnalysisJob job = runningJob();
        job.setStatus("SUCCEEDED");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals(RecordingAnalysisClaimDisposition.TERMINAL, result.disposition());
        assertEquals("SUCCEEDED", result.job().getStatus());
        assertEquals(null, result.leaseToken());
    }

    @Test
    void returnsRetryPendingWhenTheJobBecomesQueuedDuringAClaimRace() {
        AnalysisJob job = runningJob();
        job.setStatus("QUEUED");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(0);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals(RecordingAnalysisClaimDisposition.RETRY_PENDING, result.disposition());
        assertEquals("QUEUED", result.job().getStatus());
        assertEquals(null, result.leaseToken());
    }

    @Test
    void reclaimsExpiredRunningJobForAnotherWorker() {
        AnalysisJob job = runningJob();
        job.setClaimedBy("worker-2");
        when(analysisJobMapper.claimQueued(eq(JOB_ID), eq("worker-1"), anyString(), eq(300L)))
                .thenReturn(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        RecordingAnalysisJobClaimResult result = service.claimForWorker(JOB_ID, "worker-1");

        assertEquals("RUNNING", result.job().getStatus());
        assertEquals("worker-2", result.job().getClaimedBy());
        assertEquals(RecordingAnalysisClaimDisposition.CLAIMED, result.disposition());
        assertNotNull(result.leaseToken());
    }

    @Test
    void rejectsMissingWorkerIdentity() {
        ApiException exception = assertThrows(ApiException.class,
                () -> service.claimForWorker(JOB_ID, " "));

        assertEquals("AUTHENTICATION_REQUIRED", exception.getCode());
        verify(analysisJobMapper, never()).claimQueued(
                anyLong(), anyString(), anyString(), anyLong());
    }

    @Test
    void rejectsTargetAccessWhenTheClaimTokenDoesNotMatch() {
        AnalysisJob job = runningJob();
        job.setClaimedBy("worker-1");
        job.setLeaseTokenHash("different-token-hash");
        job.setClaimExpiresAt(Instant.now().plusSeconds(60));
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        ApiException exception = assertThrows(ApiException.class,
                () -> service.requireActiveWorkerJob(JOB_ID, "worker-1", "wrong-token"));

        assertEquals("WORKER_LEASE_CONFLICT", exception.getCode());
    }

    @Test
    void renewsOnlyTheCurrentWorkerLease() {
        when(analysisJobMapper.renewWorkerLease(
                eq(JOB_ID), eq("worker-1"), anyString(), any(Instant.class))).thenReturn(1);
        Instant before = Instant.now();

        Instant renewedUntil = service.renewLease(JOB_ID, "worker-1", "claim-token-1");

        assertTrue(renewedUntil.isAfter(before.plusSeconds(299)));
        verify(analysisJobMapper).renewWorkerLease(
                eq(JOB_ID), eq("worker-1"), anyString(), any(Instant.class));
    }

    private AnalysisJob runningJob() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("RUNNING");
        return job;
    }
}
