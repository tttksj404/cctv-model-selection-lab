package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.config.RecordingAnalysisProperties;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisJobLeaseRecoveryService {

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingAnalysisJobPublisher publisher;
    private final long claimLeaseSeconds;
    private final int recoveryBatchSize;

    public RecordingAnalysisJobLeaseRecoveryService(
            AnalysisJobMapper analysisJobMapper,
            RecordingAnalysisJobPublisher publisher,
            RecordingAnalysisProperties properties) {
        this.analysisJobMapper = analysisJobMapper;
        this.publisher = publisher;
        this.claimLeaseSeconds = properties.getWorkerClaimLeaseSeconds();
        this.recoveryBatchSize = properties.getLeaseRecovery().getBatchSize();
    }

    @Transactional
    public void recoverExpiredJobs() {
        List<AnalysisJob> expiredJobs = analysisJobMapper.findExpiredRecordingAnalysisJobsForRecovery(
                recoveryBatchSize, claimLeaseSeconds);
        for (AnalysisJob job : expiredJobs) {
            if (analysisJobMapper.requeueExpiredRecordingAnalysisJob(
                    job.getId(), claimLeaseSeconds) == 1) {
                publisher.enqueue(job.getId(), job.getCaseId());
            }
        }
    }
}
