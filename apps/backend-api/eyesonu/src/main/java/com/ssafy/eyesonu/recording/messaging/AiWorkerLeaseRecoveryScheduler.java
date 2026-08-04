package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.service.AiWorkerLeaseRecoveryService;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(
        prefix = "eyesonu.ai-worker.lease-recovery",
        name = "auto-start",
        havingValue = "true",
        matchIfMissing = true)
public class AiWorkerLeaseRecoveryScheduler {

    private final AiWorkerLeaseRecoveryService recoveryService;

    public AiWorkerLeaseRecoveryScheduler(AiWorkerLeaseRecoveryService recoveryService) {
        this.recoveryService = recoveryService;
    }

    @Scheduled(fixedDelayString = "${eyesonu.ai-worker.lease-recovery.fixed-delay-ms:15000}")
    public void recoverExpiredLeases() {
        recoveryService.recoverExpiredLeases();
    }
}
