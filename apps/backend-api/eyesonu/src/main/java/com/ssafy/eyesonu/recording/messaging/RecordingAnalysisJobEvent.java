package com.ssafy.eyesonu.recording.messaging;

import java.time.Instant;

public record RecordingAnalysisJobEvent(
        String commandId,
        String eventType,
        Long jobId,
        Instant occurredAt) {
}
