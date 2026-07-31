package com.ssafy.eyesonu.recording.dto.admin;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

public record RecordingAnalysisJobCreateRequest(
        @NotNull @Positive Long conditionId,
        @NotNull @Positive Long recordingId) {
}
