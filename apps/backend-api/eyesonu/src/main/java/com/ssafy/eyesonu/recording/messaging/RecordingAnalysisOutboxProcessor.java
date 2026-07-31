package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import java.time.Instant;
import java.util.List;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class RecordingAnalysisOutboxProcessor {
    private final RabbitTemplate rabbitTemplate;
    private final RecordingAnalysisOutboxMapper outboxMapper;

    public RecordingAnalysisOutboxProcessor(
            RabbitTemplate rabbitTemplate,
            RecordingAnalysisOutboxMapper outboxMapper) {
        this.rabbitTemplate = rabbitTemplate;
        this.outboxMapper = outboxMapper;
    }

    @Transactional
    public boolean publishOne() {
        List<RecordingAnalysisOutbox> ready = outboxMapper.findReady(1);
        if (ready.isEmpty()) return false;

        RecordingAnalysisOutbox outbox = ready.get(0);
        try {
            RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                    outbox.getCommandId(), outbox.getEventType(), outbox.getJobId(),
                    outbox.getCaseId(), outbox.getOccurredAt());
            rabbitTemplate.convertAndSend(
                    RecordingAnalysisJobPublisher.EXCHANGE,
                    RecordingAnalysisJobPublisher.ROUTING_KEY,
                    event,
                    message -> {
                        message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                        return message;
                    });
            outboxMapper.markPublished(outbox.getId(), Instant.now());
        } catch (RuntimeException exception) {
            outboxMapper.markFailed(outbox.getId(), exception.getMessage());
        }
        return true;
    }
}
