package com.ssafy.eyesonu.recording.service;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.config.RecordingAnalysisProperties;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobLeaseRecoveryServiceTests {

    @Mock
    private AnalysisJobMapper analysisJobMapper;

    @Mock
    private RecordingAnalysisJobPublisher publisher;

    private RecordingAnalysisJobLeaseRecoveryService service;

    @BeforeEach
    void setUp() {
        service = new RecordingAnalysisJobLeaseRecoveryService(
                analysisJobMapper, publisher, properties(300, 50));
    }

    @Test
    void recreatesOutboxWorkForAnExpiredWorkerLease() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        when(analysisJobMapper.findExpiredRecordingAnalysisJobsForRecovery(50, 300))
                .thenReturn(List.of(job));
        when(analysisJobMapper.requeueExpiredRecordingAnalysisJob(5001L, 300)).thenReturn(1);

        service.recoverExpiredJobs();

        verify(publisher).enqueue(5001L, 101L);
    }

    @Test
    void doesNotPublishWhenTheLeaseWasRenewedBeforeRecovery() {
        AnalysisJob job = new AnalysisJob();
        job.setId(5001L);
        job.setCaseId(101L);
        when(analysisJobMapper.findExpiredRecordingAnalysisJobsForRecovery(50, 300))
                .thenReturn(List.of(job));
        when(analysisJobMapper.requeueExpiredRecordingAnalysisJob(5001L, 300)).thenReturn(0);

        service.recoverExpiredJobs();

        verify(publisher, never()).enqueue(5001L, 101L);
    }

    @Test
    void usesConfiguredRecoveryBatchAndLeaseDuration() {
        service = new RecordingAnalysisJobLeaseRecoveryService(
                analysisJobMapper, publisher, properties(123, 7));
        when(analysisJobMapper.findExpiredRecordingAnalysisJobsForRecovery(7, 123))
                .thenReturn(List.of());

        service.recoverExpiredJobs();

        verify(analysisJobMapper).findExpiredRecordingAnalysisJobsForRecovery(7, 123);
    }

    private RecordingAnalysisProperties properties(long workerClaimLeaseSeconds, int batchSize) {
        RecordingAnalysisProperties properties = new RecordingAnalysisProperties();
        properties.setWorkerClaimLeaseSeconds(workerClaimLeaseSeconds);
        properties.getLeaseRecovery().setBatchSize(batchSize);
        return properties;
    }
}
