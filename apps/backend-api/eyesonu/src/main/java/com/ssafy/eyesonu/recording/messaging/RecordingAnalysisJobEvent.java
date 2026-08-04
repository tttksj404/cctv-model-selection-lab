package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;

/**
 * Notification-only event for the notebook AI Worker queue.
 *
 * <p>The broker is deliberately not a transport for prompts, recording keys,
 * camera metadata, thresholds, or signed URLs. A worker claims {@code jobId}
 * from the central server and receives those details over its authenticated
 * API call. This keeps broker messages small and prevents a stale message
 * from containing a previous revision of a search condition.</p>
 */
public record RecordingAnalysisJobEvent(
        String schemaVersion,
        String eventId,
        Long jobId,
        Long caseId,
        int attempt,
        Instant occurredAt) {

    public static final String SCHEMA_VERSION = "eyesonu-ai-worker-event-v1";

    /**
     * Compatibility constructor for callers that still use the previous
     * command/event naming. Those values intentionally do not cross the
     * notebook-worker broker boundary.
     */
    public RecordingAnalysisJobEvent(
            String eventId, String ignoredEventType, Long jobId, Long caseId, Instant occurredAt) {
        this(SCHEMA_VERSION, eventId, jobId, caseId, 1, occurredAt);
    }
}
