package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.UUID;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.context.ApplicationEventPublisher;
import org.springframework.stereotype.Component;
import org.springframework.transaction.event.TransactionPhase;
import org.springframework.transaction.event.TransactionalEventListener;

@Component
public class RecordingAnalysisJobPublisher {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";

    private final ApplicationEventPublisher applicationEventPublisher;
    private final RabbitTemplate rabbitTemplate;

    public RecordingAnalysisJobPublisher(
            ApplicationEventPublisher applicationEventPublisher,
            RabbitTemplate rabbitTemplate) {
        this.applicationEventPublisher = applicationEventPublisher;
        this.rabbitTemplate = rabbitTemplate;
    }

    public void publish(Long jobId, Long caseId) {
        applicationEventPublisher.publishEvent(new RecordingAnalysisJobEvent(
                UUID.randomUUID().toString(), EVENT_TYPE, jobId, caseId, Instant.now()));
    }

    @TransactionalEventListener(phase = TransactionPhase.AFTER_COMMIT)
    public void publishToRecordingQueue(RecordingAnalysisJobEvent event) {
        rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
            message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
            return message;
        });
    }
}
