package com.ssafy.eyesonu.recording.messaging;

import org.springframework.amqp.rabbit.annotation.RabbitListener;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.stereotype.Component;

/**
 * RabbitMQ adapter for recording analysis jobs. The consumer remains a regular
 * bean so its dependencies are validated even when listener infrastructure is
 * disabled for tests.
 */
@Component
@ConditionalOnProperty(
        prefix = "recording.analysis.consumer",
        name = "auto-start",
        havingValue = "true",
        matchIfMissing = true)
public class RecordingAnalysisJobListener {

    private final RecordingAnalysisJobConsumer consumer;

    public RecordingAnalysisJobListener(RecordingAnalysisJobConsumer consumer) {
        this.consumer = consumer;
    }

    @RabbitListener(
            queues = RecordingAnalysisJobPublisher.QUEUE,
            containerFactory = "recordingAnalysisJobListenerContainerFactory")
    public void consume(RecordingAnalysisJobEvent event) {
        consumer.consume(event);
    }
}
