package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.UUID;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import org.springframework.stereotype.Component;
import org.springframework.scheduling.annotation.Scheduled;

@Component
public class RecordingAnalysisJobPublisher {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";
    public static final String DEAD_LETTER_EXCHANGE = "search.target.dlx";
    public static final String DEAD_LETTER_QUEUE = QUEUE + ".dlq";
    public static final String DEAD_LETTER_ROUTING_KEY = ROUTING_KEY + ".dlq";

    private final RecordingAnalysisOutboxMapper outboxMapper;
    private final RecordingAnalysisOutboxProcessor processor;

    public RecordingAnalysisJobPublisher(
            RecordingAnalysisOutboxMapper outboxMapper,
            RecordingAnalysisOutboxProcessor processor) {
        this.outboxMapper = outboxMapper;
        this.processor = processor;
    }

    public void enqueue(Long jobId, Long caseId) {
        outboxMapper.insert(new RecordingAnalysisOutbox(
                null, UUID.randomUUID().toString(), EVENT_TYPE, jobId, caseId, Instant.now(), 0));
    }

    @Scheduled(fixedDelayString = "${recording.analysis.outbox.poll-delay-ms:1000}")
    public void publishPending() {
        for (int i = 0; i < 50 && processor.publishOne(); i++) {
            // Process one row per transaction so a slow broker cannot hold a batch lock.
        }
    }
}
