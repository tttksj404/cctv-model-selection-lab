package com.ssafy.eyesonu.recording.dto.device;

import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import java.time.LocalDateTime;

public record RecordingCreateRequest(
        @NotNull LocalDateTime startTime,
        @NotNull LocalDateTime endTime,
        String objectKey,
        @PositiveOrZero Long fileSize) {
}
