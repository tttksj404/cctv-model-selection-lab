package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.ScheduledFuture;
import java.util.concurrent.TimeUnit;
import java.util.UUID;
import java.util.concurrent.atomic.AtomicBoolean;
import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import org.springframework.amqp.core.MessageDeliveryMode;
import org.springframework.amqp.core.ReturnedMessage;
import org.springframework.amqp.rabbit.connection.CorrelationData;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Value;
import jakarta.annotation.PreDestroy;

@Component
public class RecordingAnalysisJobPublisher implements AutoCloseable {

    public static final String EVENT_TYPE = "RECORDING_ANALYSIS_JOB_CREATED";
    public static final String QUEUE = "search.target.recording.queue";
    public static final String ROUTING_KEY = "search.target.recording.created";
    public static final String EXCHANGE = "search.target.exchange";
    public static final String DEAD_LETTER_EXCHANGE = "search.target.dlx";
    public static final String DEAD_LETTER_QUEUE = QUEUE + ".dlq";
    public static final String DEAD_LETTER_ROUTING_KEY = ROUTING_KEY + ".dlq";
    private static final long CONFIRM_TIMEOUT_SECONDS = 5L;

    private final RabbitTemplate rabbitTemplate;
    private final RecordingAnalysisOutboxMapper outboxMapper;
    private final RecordingAnalysisOutboxClaimer outboxClaimer;
    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final long claimLeaseSeconds;
    private final Object heartbeatExecutorMonitor = new Object();
    private ScheduledExecutorService heartbeatExecutor;

    public RecordingAnalysisJobPublisher(
            RabbitTemplate rabbitTemplate,
            RecordingAnalysisOutboxMapper outboxMapper,
            RecordingAnalysisOutboxClaimer outboxClaimer,
            AnalysisJobMapper analysisJobMapper,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            @Value("${recording.analysis.outbox.claim-lease-seconds:300}") long claimLeaseSeconds) {
        this.rabbitTemplate = rabbitTemplate;
        this.outboxMapper = outboxMapper;
        this.outboxClaimer = outboxClaimer;
        this.analysisJobMapper = analysisJobMapper;
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.claimLeaseSeconds = claimLeaseSeconds;
    }

    @PreDestroy
    @Override
    public void close() {
        synchronized (heartbeatExecutorMonitor) {
            if (heartbeatExecutor != null) {
                heartbeatExecutor.shutdownNow();
                heartbeatExecutor = null;
            }
        }
    }

    public void enqueue(Long jobId, Long caseId) {
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null || !caseId.equals(job.getCaseId())) {
            throw new IllegalStateException("Recording analysis job could not be loaded for publishing: " + jobId);
        }
        Recording recording = recordingMapper.findById(job.getRecordingId());
        if (recording == null) {
            throw new IllegalStateException("Recording could not be loaded for publishing: " + job.getRecordingId());
        }
        Camera camera = cameraMapper.findById(recording.getCameraId()).orElseThrow(() ->
                new IllegalStateException("Camera could not be loaded for publishing: " + recording.getCameraId()));

        RecordingAnalysisOutbox outbox = new RecordingAnalysisOutbox();
        outbox.setCommandId(UUID.randomUUID().toString());
        outbox.setEventType(EVENT_TYPE);
        outbox.setJobId(jobId);
        outbox.setCaseId(caseId);
        outbox.setRecordingId(recording.getId());
        outbox.setCameraId(camera.id());
        outbox.setCameraCode(camera.cameraCode());
        outbox.setCameraName(camera.cameraName());
        outbox.setRecordingObjectKey(recording.getS3Key());
        outbox.setPrompt(job.getPromptSnapshot());
        outbox.setExclusionPrompt(job.getExclusionPromptSnapshot());
        outbox.setSimilarityThreshold(job.getSimilarityThresholdSnapshot());
        outbox.setSearchStart(job.getSearchStartSnapshot());
        outbox.setSearchEnd(job.getSearchEndSnapshot());
        outbox.setSearchArea(job.getSearchAreaSnapshot());
        outbox.setAttempt(job.getRetryCount() + 1);
        outbox.setOccurredAt(Instant.now());
        outboxMapper.insert(outbox);
    }

    public void publishPending() {
        for (int published = 0; published < 50; published++) {
            ClaimedRecordingAnalysisOutbox claimed = outboxClaimer.claimNext().orElse(null);
            if (claimed == null) {
                return;
            }
            RecordingAnalysisOutbox outbox = claimed.outbox();
            AtomicBoolean leaseOwned = new AtomicBoolean(true);
            ScheduledFuture<?> heartbeat = startHeartbeat(
                    outbox, claimed.claimToken(), leaseOwned);
            try {
                RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                        outbox.getCommandId(), outbox.getEventType(), outbox.getJobId(),
                        outbox.getCaseId(), outbox.getRecordingId(), outbox.getCameraId(),
                        outbox.getCameraCode(), outbox.getCameraName(), outbox.getRecordingObjectKey(),
                        outbox.getPrompt(), outbox.getExclusionPrompt(), outbox.getSimilarityThreshold(),
                        outbox.getSearchStart(), outbox.getSearchEnd(), outbox.getSearchArea(),
                        outbox.getAttempt(), outbox.getOccurredAt());
                CorrelationData correlationData = new CorrelationData(outbox.getCommandId());
                ensureLeaseOwned(leaseOwned);
                rabbitTemplate.convertAndSend(EXCHANGE, ROUTING_KEY, event, message -> {
                    message.getMessageProperties().setDeliveryMode(MessageDeliveryMode.PERSISTENT);
                    return message;
                }, correlationData);
                ensureLeaseOwned(leaseOwned);
                awaitBrokerAcceptance(correlationData, leaseOwned);
                outboxMapper.markPublished(outbox.getId(), claimed.claimToken(), Instant.now());
            } catch (LeaseOwnershipLostException exception) {
                return;
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
                outboxMapper.markFailed(
                        outbox.getId(), claimed.claimToken(),
                        "RabbitMQ publisher confirm was interrupted");
                return;
            } catch (Exception exception) {
                outboxMapper.markFailed(
                        outbox.getId(), claimed.claimToken(), failureMessage(exception));
            } finally {
                heartbeat.cancel(false);
            }
        }
    }

    private ScheduledFuture<?> startHeartbeat(
            RecordingAnalysisOutbox outbox,
            String claimToken,
            AtomicBoolean leaseOwned) {
        renewLease(outbox.getId(), claimToken, leaseOwned);
        if (!leaseOwned.get()) {
            return heartbeatExecutor().schedule(() -> { }, 0, TimeUnit.MILLISECONDS);
        }
        long intervalSeconds = Math.max(1L, claimLeaseSeconds / 3L);
        return heartbeatExecutor().scheduleAtFixedRate(
                () -> renewLease(outbox.getId(), claimToken, leaseOwned),
                intervalSeconds,
                intervalSeconds,
                TimeUnit.SECONDS);
    }

    private ScheduledExecutorService heartbeatExecutor() {
        synchronized (heartbeatExecutorMonitor) {
            if (heartbeatExecutor == null || heartbeatExecutor.isShutdown()) {
                heartbeatExecutor = Executors.newSingleThreadScheduledExecutor(runnable -> {
                    Thread thread = new Thread(runnable, "recording-analysis-outbox-heartbeat");
                    thread.setDaemon(true);
                    return thread;
                });
            }
            return heartbeatExecutor;
        }
    }

    private void renewLease(Long outboxId, String claimToken, AtomicBoolean leaseOwned) {
        try {
            int renewed = outboxMapper.renewLease(
                    outboxId,
                    claimToken,
                    Instant.now().plusSeconds(claimLeaseSeconds));
            if (renewed != 1) {
                leaseOwned.set(false);
            }
        } catch (RuntimeException ignored) {
            leaseOwned.set(false);
        }
    }

    private void awaitBrokerAcceptance(
            CorrelationData correlationData,
            AtomicBoolean leaseOwned) throws Exception {
        long deadline = System.nanoTime()
                + TimeUnit.SECONDS.toNanos(CONFIRM_TIMEOUT_SECONDS);
        CorrelationData.Confirm confirm;
        while (true) {
            ensureLeaseOwned(leaseOwned);
            long remainingNanos = deadline - System.nanoTime();
            if (remainingNanos <= 0) {
                throw new java.util.concurrent.TimeoutException("RabbitMQ publisher confirm timed out");
            }
            try {
                confirm = correlationData.getFuture().get(
                        Math.min(TimeUnit.NANOSECONDS.toMillis(remainingNanos), 200L),
                        TimeUnit.MILLISECONDS);
                break;
            } catch (java.util.concurrent.TimeoutException ignored) {
                // Re-check ownership while waiting for the broker.
            }
        }
        ensureLeaseOwned(leaseOwned);
        if (!confirm.ack()) {
            throw new IllegalStateException("RabbitMQ publisher NACK: " + confirm.reason());
        }
        ReturnedMessage returned = correlationData.getReturned();
        if (returned != null) {
            throw new IllegalStateException("RabbitMQ message was returned: " + returned.getReplyText());
        }
    }

    private void ensureLeaseOwned(AtomicBoolean leaseOwned) {
        if (!leaseOwned.get()) {
            throw new LeaseOwnershipLostException();
        }
    }

    private static class LeaseOwnershipLostException extends RuntimeException {
    }

    private String failureMessage(Exception exception) {
        String message = exception.getMessage();
        return message == null || message.isBlank() ? exception.getClass().getSimpleName() : message;
    }
}
