package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimService;
import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

/**
 * Receives recording-analysis commands and atomically claims the referenced
 * job before the worker starts its analysis.
 */
@Component
@ConditionalOnProperty(
        prefix = "recording.analysis.consumer",
        name = "enabled",
        havingValue = "true",
        matchIfMissing = true)
public class RecordingAnalysisJobConsumer {

    private static final Logger log = LoggerFactory.getLogger(RecordingAnalysisJobConsumer.class);

    private final RecordingAnalysisJobClaimService claimService;

    public RecordingAnalysisJobConsumer(RecordingAnalysisJobClaimService claimService) {
        this.claimService = claimService;
    }

    @RabbitListener(
            queues = RecordingAnalysisJobPublisher.QUEUE,
            containerFactory = "recordingAnalysisJobListenerContainerFactory",
            autoStartup = "${recording.analysis.consumer.auto-start:true}")
    public void consume(RecordingAnalysisJobEvent event) {
        if (event == null || event.jobId() == null) {
            log.warn("Ignoring malformed recording analysis event without jobId: {}", event);
            return;
        }

        claimService.claim(event.jobId());
    }
}
