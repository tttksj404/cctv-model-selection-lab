package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
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
        service = new RecordingAnalysisJobClaimService(analysisJobMapper);
    }

    @Test
    void claimsOnlyQueuedJobAndReloadsRunningSnapshot() {
        AnalysisJob job = new AnalysisJob();
        job.setId(JOB_ID);
        job.setJobType("RECORDING_ANALYSIS");
        job.setStatus("RUNNING");
        when(analysisJobMapper.claimQueued(JOB_ID)).thenReturn(1);
        when(analysisJobMapper.findRecordingAnalysisById(JOB_ID)).thenReturn(job);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isPresent());
        assertEquals("RUNNING", result.orElseThrow().getStatus());
        verify(analysisJobMapper).claimQueued(JOB_ID);
        verify(analysisJobMapper).findRecordingAnalysisById(JOB_ID);
    }

    @Test
    void returnsEmptyWhenAnotherWorkerAlreadyClaimedJob() {
        when(analysisJobMapper.claimQueued(JOB_ID)).thenReturn(0);

        Optional<AnalysisJob> result = service.claim(JOB_ID);

        assertTrue(result.isEmpty());
        verify(analysisJobMapper, never()).findRecordingAnalysisById(JOB_ID);
    }
}
