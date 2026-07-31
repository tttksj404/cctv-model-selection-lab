package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.UUID;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@Component
public class RecordingAnalysisJobPublisher {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";

    private final RabbitTemplate rabbitTemplate;

    public RecordingAnalysisJobPublisher(RabbitTemplate rabbitTemplate) {
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publishAfterCommit(Long jobId, Long caseId) {
        if (!TransactionSynchronizationManager.isSynchronizationActive()) {
            throw new IllegalStateException(
                    "Recording analysis job events must be published inside a transaction");
        }
        TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
            @Override
            public void afterCommit() {
                RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                        UUID.randomUUID().toString(), EVENT_TYPE, jobId, caseId, Instant.now());
                rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
                    message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    return message;
                });
            }
        });
    }
}
