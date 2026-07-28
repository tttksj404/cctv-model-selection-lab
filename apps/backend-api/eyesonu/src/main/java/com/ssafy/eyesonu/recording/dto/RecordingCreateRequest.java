package com.ssafy.eyesonu.recording.dto;

import com.ssafy.eyesonu.recording.domain.UploadStatus;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;
import java.time.LocalDateTime;

public record RecordingCreateRequest(
        @NotNull LocalDateTime startTime,
        @NotNull LocalDateTime endTime,
        String objectKey,
        @PositiveOrZero Long fileSize,
        @NotNull UploadStatus uploadStatus) {
}
