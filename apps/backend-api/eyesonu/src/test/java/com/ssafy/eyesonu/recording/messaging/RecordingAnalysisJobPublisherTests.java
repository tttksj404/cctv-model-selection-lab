package com.ssafy.eyesonu.recording.messaging;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.mockito.Mockito.doThrow;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobPublisherTests {

    @Mock
    private RabbitTemplate rabbitTemplate;

    @Mock
    private RecordingAnalysisOutboxMapper outboxMapper;

    @Test
    void storesOutboxWithStableCommandIdBeforePublishing() {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper);

        publisher.enqueue(5001L, 101L);

        verify(outboxMapper).insert(any(RecordingAnalysisOutbox.class));
        verify(rabbitTemplate, org.mockito.Mockito.never())
                .convertAndSend(any(), any(), any(), any(MessagePostProcessor.class));
    }

    @Test
    void publishesReadyOutboxAndMarksItPublished() {
        Instant occurredAt = Instant.parse("2026-07-31T04:00:00Z");
        RecordingAnalysisOutbox outbox = new RecordingAnalysisOutbox(
                1L, "cmd-1", RecordingAnalysisJobPublisher.EVENT_TYPE,
                5001L, 101L, occurredAt, 0);
        when(outboxMapper.findReady(50)).thenReturn(List.of(outbox));
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper);

        publisher.publishPending();

        verify(rabbitTemplate).convertAndSend(
                eq(RecordingAnalysisJobPublisher.EXCHANGE),
                eq(RecordingAnalysisJobPublisher.ROUTING_KEY),
                any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class));
        verify(outboxMapper).markPublished(eq(1L), any(Instant.class));
    }

    @Test
    void keepsOutboxPendingAndSchedulesRetryWhenPublishingFails() {
        Instant occurredAt = Instant.parse("2026-07-31T04:00:00Z");
        RecordingAnalysisOutbox outbox = new RecordingAnalysisOutbox(
                1L, "cmd-1", RecordingAnalysisJobPublisher.EVENT_TYPE,
                5001L, 101L, occurredAt, 0);
        when(outboxMapper.findReady(50)).thenReturn(List.of(outbox));
        doThrow(new IllegalStateException("RabbitMQ unavailable"))
                .when(rabbitTemplate).convertAndSend(
                any(String.class), any(String.class), any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class));
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper);

        publisher.publishPending();

        verify(outboxMapper).markFailed(eq(1L), eq("RabbitMQ unavailable"));
    }
}
