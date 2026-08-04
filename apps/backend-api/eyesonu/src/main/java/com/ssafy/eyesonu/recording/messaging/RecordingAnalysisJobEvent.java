package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;
public record RecordingAnalysisJobEvent(
        String schemaVersion,
        String eventId,
        Long jobId,
        Long caseId,
        int attempt,
        Instant occurredAt) {

    public static final String SCHEMA_VERSION = "eyesonu-ai-worker-event-v1";

    /**
     * Compatibility constructor for the previous internal consumer tests. The
     * event type deliberately does not cross the broker boundary: the worker
     * receives only the routing identity and loads all sensitive job details
     * through its authenticated central-server claim request.
     */
    public RecordingAnalysisJobEvent(
            String eventId, String ignoredEventType, Long jobId, Long caseId, Instant occurredAt) {
        this(SCHEMA_VERSION, eventId, jobId, caseId, 1, occurredAt);
    }
}
