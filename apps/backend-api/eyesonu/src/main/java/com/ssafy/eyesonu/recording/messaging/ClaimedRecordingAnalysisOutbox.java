package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;

public record ClaimedRecordingAnalysisOutbox(
        RecordingAnalysisOutbox outbox,
        String claimToken) {
}
