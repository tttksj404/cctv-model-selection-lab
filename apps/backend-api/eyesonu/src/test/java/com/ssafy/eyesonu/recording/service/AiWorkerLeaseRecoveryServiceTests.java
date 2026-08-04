package com.ssafy.eyesonu.recording.service;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class AiWorkerLeaseRecoveryServiceTests {

    @Mock private AnalysisJobMapper analysisJobMapper;
    @Mock private RecordingAnalysisJobPublisher publisher;

    @Test
    void requeuesExpiredLeaseWithinRetryBudgetAndFailsExhaustedLease() {
        AnalysisJob retryable = job(5001L, 101L, 2);
        AnalysisJob exhausted = job(5002L, 102L, 3);
        AiWorkerProperties properties = new AiWorkerProperties();
        properties.setMaxRetryCount(3);
        when(analysisJobMapper.findExpiredRunningForRecovery(50))
                .thenReturn(List.of(retryable, exhausted));
        when(analysisJobMapper.recoverExpired(5001L, "QUEUED", "AI Worker lease expired before completion"))
                .thenReturn(1);
        when(analysisJobMapper.recoverExpired(5002L, "FAILED", "AI Worker lease expired before completion"))
                .thenReturn(1);

        new AiWorkerLeaseRecoveryService(analysisJobMapper, publisher, properties)
                .recoverExpiredLeases();

        verify(publisher).enqueue(5001L, 101L);
        verify(publisher, never()).enqueue(5002L, 102L);
    }

    private AnalysisJob job(Long id, Long caseId, int retryCount) {
        AnalysisJob job = new AnalysisJob();
        job.setId(id);
        job.setCaseId(caseId);
        job.setRetryCount(retryCount);
        return job;
    }
}
