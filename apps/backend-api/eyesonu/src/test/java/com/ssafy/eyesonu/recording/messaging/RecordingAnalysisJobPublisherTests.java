package com.ssafy.eyesonu.recording.messaging;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.amqp.core.Message;
import org.springframework.amqp.core.MessagePostProcessor;
import org.springframework.amqp.core.ReturnedMessage;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobPublisherTests {

    @Mock
    private RabbitTemplate rabbitTemplate;

    @Mock
    private RecordingAnalysisOutboxMapper outboxMapper;

    @Mock
    private RecordingAnalysisOutboxClaimer outboxClaimer;

    @Test
    void storesOutboxWithStableCommandIdBeforePublishing() {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 300);

        publisher.enqueue(5001L, 101L);

        verify(outboxMapper).insert(any(RecordingAnalysisOutbox.class));
        verify(rabbitTemplate, never()).convertAndSend(
                anyString(), anyString(), any(), any(MessagePostProcessor.class), any(CorrelationData.class));
    }

    @Test
    void marksPublishedOnlyAfterBrokerAckWithoutReturn() {
        RecordingAnalysisOutbox outbox = readyOutbox();
        claim(outbox);
        completeConfirm(true, null, null);

        new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 300).publishPending();

        verify(rabbitTemplate).convertAndSend(
                eq(RecordingAnalysisJobPublisher.EXCHANGE),
                eq(RecordingAnalysisJobPublisher.ROUTING_KEY),
                any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class),
                any(CorrelationData.class));
        verify(outboxMapper).markPublished(eq(1L), eq("claim-1"), any(Instant.class));
        verify(outboxMapper, never()).markFailed(any(), anyString(), anyString());
    }

    @Test
    void schedulesRetryWhenBrokerNacksMessage() {
        claim(readyOutbox());
        completeConfirm(false, "exchange unavailable", null);

        new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 300).publishPending();

        verify(outboxMapper).markFailed(
                1L, "claim-1", "RabbitMQ publisher NACK: exchange unavailable");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void schedulesRetryWhenMessageIsReturnedAsUnroutable() {
        claim(readyOutbox());
        ReturnedMessage returned = new ReturnedMessage(
                new Message(new byte[0]), 312, "NO_ROUTE",
                RecordingAnalysisJobPublisher.EXCHANGE,
                RecordingAnalysisJobPublisher.ROUTING_KEY);
        completeConfirm(true, null, returned);

        new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 300).publishPending();

        verify(outboxMapper).markFailed(1L, "claim-1", "RabbitMQ message was returned: NO_ROUTE");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void schedulesRetryWhenPublishingThrows() {
        claim(readyOutbox());
        doThrow(new IllegalStateException("RabbitMQ unavailable"))
                .when(rabbitTemplate).convertAndSend(
                        anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                        any(MessagePostProcessor.class), any(CorrelationData.class));

        new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 300).publishPending();

        verify(outboxMapper).markFailed(1L, "claim-1", "RabbitMQ unavailable");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void renewsLeaseWhileBrokerConfirmationIsSlow() {
        claim(readyOutbox());
        doAnswer(invocation -> {
            Thread.sleep(1200L);
            CorrelationData correlationData = invocation.getArgument(4);
            correlationData.getFuture().complete(new CorrelationData.Confirm(true, null));
            return null;
        }).when(rabbitTemplate).convertAndSend(
                anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class), any(CorrelationData.class));

        new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer, 3).publishPending();

        verify(outboxMapper, atLeastOnce()).renewLease(
                eq(1L), eq("claim-1"), any(Instant.class));
    }

    private void completeConfirm(boolean ack, String reason, ReturnedMessage returned) {
        doAnswer(invocation -> {
            CorrelationData correlationData = invocation.getArgument(4);
            if (returned != null) correlationData.setReturned(returned);
            correlationData.getFuture().complete(new CorrelationData.Confirm(ack, reason));
            return null;
        }).when(rabbitTemplate).convertAndSend(
                anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class), any(CorrelationData.class));
    }

    private void claim(RecordingAnalysisOutbox outbox) {
        when(outboxClaimer.claimNext()).thenReturn(
                Optional.of(new ClaimedRecordingAnalysisOutbox(outbox, "claim-1")),
                Optional.empty());
    }

    private RecordingAnalysisOutbox readyOutbox() {
        return new RecordingAnalysisOutbox(
                1L, "cmd-1", RecordingAnalysisJobPublisher.EVENT_TYPE,
                5001L, 101L, Instant.parse("2026-07-31T04:00:00Z"), 0);
    }
}
