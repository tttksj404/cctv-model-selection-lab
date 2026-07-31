package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.concurrent.TimeUnit;
import java.util.UUID;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.ReturnedMessage;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.scheduling.annotation.Scheduled;

@Component
public class RecordingAnalysisJobPublisher {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";
    private static final long CONFIRM_TIMEOUT_SECONDS = 5L;

    private final RabbitTemplate rabbitTemplate;
    private final RecordingAnalysisOutboxMapper outboxMapper;

    public RecordingAnalysisJobPublisher(
            RabbitTemplate rabbitTemplate,
            RecordingAnalysisOutboxMapper outboxMapper) {
        this.rabbitTemplate = rabbitTemplate;
        this.outboxMapper = outboxMapper;
    }

    public void enqueue(Long jobId, Long caseId) {
        outboxMapper.insert(new RecordingAnalysisOutbox(
                null, UUID.randomUUID().toString(), EVENT_TYPE, jobId, caseId, Instant.now(), 0));
    }

    @Scheduled(fixedDelayString = "${recording.analysis.outbox.poll-delay-ms:1000}")
    public void publishPending() {
        for (RecordingAnalysisOutbox outbox : outboxMapper.findReady(50)) {
            try {
                RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                        outbox.getCommandId(), outbox.getEventType(), outbox.getJobId(),
                        outbox.getCaseId(), outbox.getOccurredAt());
                CorrelationData correlationData = new CorrelationData(outbox.getCommandId());
                rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
                    message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    return message;
                }, correlationData);
                awaitBrokerAcceptance(correlationData);
                outboxMapper.markPublished(outbox.getId(), Instant.now());
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                outboxMapper.markFailed(outbox.getId(), "RabbitMQ publisher confirm was interrupted");
                return;
            } catch (Exception exception) {
                outboxMapper.markFailed(outbox.getId(), failureMessage(exception));
            }
        }
    }

    private void awaitBrokerAcceptance(CorrelationData correlationData) throws Exception {
        CorrelationData.Confirm confirm = correlationData.getFuture()
                .get(CONFIRM_TIMEOUT_SECONDS, TimeUnit.SECONDS);
        if (!confirm.ack()) {
            throw new IllegalStateException("RabbitMQ publisher NACK: " + confirm.reason());
        }
        ReturnedMessage returned = correlationData.getReturned();
        if (returned != null) {
            throw new IllegalStateException("RabbitMQ message was returned: " + returned.getReplyText());
        }
    }

    private String failureMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank() ? exception.getClass().getSimpleName() : message;
    }
}
