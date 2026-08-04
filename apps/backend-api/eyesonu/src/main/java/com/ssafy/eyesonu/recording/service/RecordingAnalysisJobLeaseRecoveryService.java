package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class RecordingAnalysisJobLeaseRecoveryService {

    private static final int RECOVERY_BATCH_SIZE = 50;

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingAnalysisJobPublisher publisher;
    private final long claimLeaseSeconds;

    public RecordingAnalysisJobLeaseRecoveryService(
            AnalysisJobMapper analysisJobMapper,
            RecordingAnalysisJobPublisher publisher,
            @Value("${recording.analysis.worker-claim-lease-seconds:300}") long claimLeaseSeconds) {
        this.analysisJobMapper = analysisJobMapper;
        this.publisher = publisher;
        this.claimLeaseSeconds = claimLeaseSeconds;
    }

    @Transactional
    public void recoverExpiredJobs() {
        List<AnalysisJob> expiredJobs = analysisJobMapper.findExpiredRecordingAnalysisJobsForRecovery(
                RECOVERY_BATCH_SIZE, claimLeaseSeconds);
        for (AnalysisJob job : expiredJobs) {
            if (analysisJobMapper.requeueExpiredRecordingAnalysisJob(
                    job.getId(), claimLeaseSeconds) == 1) {
                publisher.enqueue(job.getId(), job.getCaseId());
            }
        }
    }
}
