package com.ssafy.eyesonu.recording.messaging;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.context.ApplicationEventPublisher;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobPublisherTests {

    @Mock
    private ApplicationEventPublisher applicationEventPublisher;

    @Mock
    private RabbitTemplate rabbitTemplate;

    @Test
    void publishesApplicationEvent() {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                applicationEventPublisher, rabbitTemplate);

        publisher.publish(5001L, 101L);

        verify(applicationEventPublisher).publishEvent(any(RecordingAnalysisJobEvent.class));
    }

    @Test
    void publishesRabbitMessageWhenTransactionListenerHandlesEvent() {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                applicationEventPublisher, rabbitTemplate);
        RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                "cmd-1", RecordingAnalysisJobPublisher.EVENT_TYPE, 5001L, 101L,
                Instant.parse("2026-07-31T04:00:00Z"));

        publisher.publishToRecordingQueue(event);

        verify(rabbitTemplate).convertAndSend(
                eq(RecordingAnalysisJobPublisher.EXCHANGE),
                eq(RecordingAnalysisJobPublisher.ROUTING_KEY),
                eq(event),
                any(MessagePostProcessor.class));
    }
}
