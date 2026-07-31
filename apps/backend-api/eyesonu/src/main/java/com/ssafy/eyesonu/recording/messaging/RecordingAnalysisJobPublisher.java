package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.UUID;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.transaction.annotation.Transactional;

@Component
public class RecordingAnalysisJobPublisher {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";

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
    @Transactional
    public void publishPending() {
        for (RecordingAnalysisOutbox outbox : outboxMapper.findReady(50)) {
            try {
                RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                        outbox.getCommandId(), outbox.getEventType(), outbox.getJobId(),
                        outbox.getCaseId(), outbox.getOccurredAt());
                rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
                    message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    return message;
                });
                outboxMapper.markPublished(outbox.getId(), Instant.now());
            } catch (RuntimeException exception) {
                outboxMapper.markFailed(outbox.getId(), exception.getMessage());
            }
        }
    }
}
