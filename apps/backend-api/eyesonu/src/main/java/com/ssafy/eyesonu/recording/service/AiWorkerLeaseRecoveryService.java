package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class AiWorkerLeaseRecoveryService {

    private static final int RECOVERY_BATCH_SIZE = 50;
    private static final String LEASE_EXPIRY_MESSAGE = "AI Worker lease expired before completion";

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingAnalysisJobPublisher publisher;
    private final AiWorkerProperties properties;

    public AiWorkerLeaseRecoveryService(
            AnalysisJobMapper analysisJobMapper,
            RecordingAnalysisJobPublisher publisher,
            AiWorkerProperties properties) {
        this.analysisJobMapper = analysisJobMapper;
        this.publisher = publisher;
        this.properties = properties;
    }

    @Transactional
    public void recoverExpiredLeases() {
        List<AnalysisJob> jobs = analysisJobMapper.findExpiredRunningForRecovery(RECOVERY_BATCH_SIZE);
        for (AnalysisJob job : jobs) {
            boolean requeue = job.getRetryCount() < properties.getMaxRetryCount();
            String nextStatus = requeue ? "QUEUED" : "FAILED";
            int updated = analysisJobMapper.recoverExpired(
                    job.getId(), nextStatus, LEASE_EXPIRY_MESSAGE);
            if (updated == 1 && requeue) {
                publisher.enqueue(job.getId(), job.getCaseId());
            }
        }
    }
}
