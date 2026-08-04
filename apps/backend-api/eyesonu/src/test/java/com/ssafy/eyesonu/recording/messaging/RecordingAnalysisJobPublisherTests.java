package com.ssafy.eyesonu.recording.messaging;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.atLeastOnce;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisPublishSnapshot;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.AfterEach;
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

    @Mock
    private AnalysisJobMapper analysisJobMapper;

    @Mock
    private final List<RecordingAnalysisJobPublisher> publishers = new ArrayList<>();

    @AfterEach
    void closePublishers() {
        publishers.forEach(RecordingAnalysisJobPublisher::close);
    }

    @Test
    void storesOutboxWithStableCommandIdBeforePublishing() {
        RecordingAnalysisJobPublisher publisher = publisher(300);
        RecordingAnalysisPublishSnapshot snapshot = new RecordingAnalysisPublishSnapshot();
        snapshot.setJobId(5001L);
        snapshot.setCaseId(101L);
        snapshot.setRecordingId(3001L);
        snapshot.setCameraId(11L);
        snapshot.setCameraCode("CAM-001");
        snapshot.setCameraName("Front");
        snapshot.setRecordingObjectKey("recordings/CAM-001/video.mp4");
        snapshot.setPrompt("person in red");
        snapshot.setAttempt(1);
        when(analysisJobMapper.findRecordingAnalysisPublishSnapshot(5001L, 101L))
                .thenReturn(snapshot);

        publisher.enqueue(5001L, 101L);

        verify(outboxMapper).insert(any(RecordingAnalysisOutbox.class));
        verify(rabbitTemplate, never()).convertAndSend(
                anyString(), anyString(), any(), any(MessagePostProcessor.class), any(CorrelationData.class));
    }

    @Test
    void recordingAnalysisEventDoesNotExposeSimilarityThreshold() {
        RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                "command-1", RecordingAnalysisJobPublisher.EVENT_TYPE,
                5001L, 101L, Instant.parse("2026-07-31T04:00:00Z"));

        var payload = new ObjectMapper().findAndRegisterModules().valueToTree(event);

        assertFalse(payload.has("similarityThreshold"));
        assertFalse(payload.has("prompt"));
        assertFalse(payload.has("exclusionPrompt"));
        assertFalse(payload.has("searchStart"));
        assertFalse(payload.has("searchEnd"));
        assertFalse(payload.has("searchArea"));
    }

    @Test
    void marksPublishedOnlyAfterBrokerAckWithoutReturn() {
        RecordingAnalysisOutbox outbox = readyOutbox();
        claim(outbox);
        stubLeaseRenewal(1);
        completeConfirm(true, null, null);

        publisher(300).publishPending();

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
        stubLeaseRenewal(1);
        completeConfirm(false, "exchange unavailable", null);

        publisher(300).publishPending();

        verify(outboxMapper).markFailed(
                1L, "claim-1", "RabbitMQ publisher NACK: exchange unavailable");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void schedulesRetryWhenMessageIsReturnedAsUnroutable() {
        claim(readyOutbox());
        stubLeaseRenewal(1);
        ReturnedMessage returned = new ReturnedMessage(
                new Message(new byte[0]), 312, "NO_ROUTE",
                RecordingAnalysisJobPublisher.EXCHANGE,
                RecordingAnalysisJobPublisher.ROUTING_KEY);
        completeConfirm(true, null, returned);

        publisher(300).publishPending();

        verify(outboxMapper).markFailed(1L, "claim-1", "RabbitMQ message was returned: NO_ROUTE");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void schedulesRetryWhenPublishingThrows() {
        claim(readyOutbox());
        stubLeaseRenewal(1);
        doThrow(new IllegalStateException("RabbitMQ unavailable"))
                .when(rabbitTemplate).convertAndSend(
                        anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                        any(MessagePostProcessor.class), any(CorrelationData.class));

        publisher(300).publishPending();

        verify(outboxMapper).markFailed(1L, "claim-1", "RabbitMQ unavailable");
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
    }

    @Test
    void renewsLeaseWhileBrokerConfirmationIsSlow() {
        claim(readyOutbox());
        stubLeaseRenewal(1);
        doAnswer(invocation -> {
            Thread.sleep(1200L);
            CorrelationData correlationData = invocation.getArgument(4);
            correlationData.getFuture().complete(new CorrelationData.Confirm(true, null));
            return null;
        }).when(rabbitTemplate).convertAndSend(
                anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class), any(CorrelationData.class));

        publisher(3).publishPending();

        verify(outboxMapper, atLeastOnce()).renewLease(
                eq(1L), eq("claim-1"), any(Instant.class));
    }

    @Test
    void stopsPublishingWhenHeartbeatLosesLeaseOwnership() {
        claim(readyOutbox());
        stubLeaseRenewal(0);

        publisher(3).publishPending();

        verify(rabbitTemplate, never()).convertAndSend(
                anyString(), anyString(), any(RecordingAnalysisJobEvent.class),
                any(MessagePostProcessor.class), any(CorrelationData.class));
        verify(outboxMapper, never()).markPublished(any(), anyString(), any());
        verify(outboxMapper, never()).markFailed(any(), anyString(), anyString());
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

    private void stubLeaseRenewal(int result) {
        when(outboxMapper.renewLease(any(), anyString(), any(Instant.class))).thenReturn(result);
    }

    private RecordingAnalysisOutbox readyOutbox() {
        RecordingAnalysisOutbox outbox = new RecordingAnalysisOutbox();
        outbox.setId(1L);
        outbox.setCommandId("cmd-1");
        outbox.setEventType(RecordingAnalysisJobPublisher.EVENT_TYPE);
        outbox.setJobId(5001L);
        outbox.setCaseId(101L);
        outbox.setRecordingId(3001L);
        outbox.setCameraId(11L);
        outbox.setCameraCode("CAM-001");
        outbox.setCameraName("Front");
        outbox.setRecordingObjectKey("recordings/CAM-001/video.mp4");
        outbox.setPrompt("person in red");
        outbox.setAttempt(1);
        outbox.setOccurredAt(Instant.parse("2026-07-31T04:00:00Z"));
        return outbox;
    }

    private RecordingAnalysisJobPublisher publisher(long claimLeaseSeconds) {
        RecordingAnalysisJobPublisher publisher = new RecordingAnalysisJobPublisher(
                rabbitTemplate, outboxMapper, outboxClaimer,
                analysisJobMapper, claimLeaseSeconds);
        publishers.add(publisher);
        return publisher;
    }
}
