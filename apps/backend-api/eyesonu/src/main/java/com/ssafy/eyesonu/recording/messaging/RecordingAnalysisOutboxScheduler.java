package com.ssafy.eyesonu.recording.messaging;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
@ConditionalOnProperty(
        prefix = "recording.analysis.outbox",
        name = "auto-start",
        havingValue = "true",
        matchIfMissing = true)
public class RecordingAnalysisOutboxScheduler {

    private final RecordingAnalysisJobPublisher publisher;

    public RecordingAnalysisOutboxScheduler(RecordingAnalysisJobPublisher publisher) {
        this.publisher = publisher;
    }

    @Scheduled(fixedDelayString = "${recording.analysis.outbox.poll-delay-ms}")
    public void publishPending() {
        publisher.publishPending();
    }
}
