package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobLeaseRecoveryService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(
        prefix = "recording.analysis.lease-recovery",
        name = "auto-start",
        havingValue = "true",
        matchIfMissing = true)
public class RecordingAnalysisJobLeaseRecoveryScheduler {

    private final RecordingAnalysisJobLeaseRecoveryService recoveryService;

    public RecordingAnalysisJobLeaseRecoveryScheduler(
            RecordingAnalysisJobLeaseRecoveryService recoveryService) {
        this.recoveryService = recoveryService;
    }

    @Scheduled(fixedDelayString = "${recording.analysis.lease-recovery.poll-delay-ms}")
    public void recoverExpiredJobs() {
        recoveryService.recoverExpiredJobs();
    }
}
