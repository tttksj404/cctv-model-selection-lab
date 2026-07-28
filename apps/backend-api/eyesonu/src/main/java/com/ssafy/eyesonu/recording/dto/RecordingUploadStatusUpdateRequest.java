package com.ssafy.eyesonu.recording.dto;

import com.ssafy.eyesonu.recording.domain.UploadStatus;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

public record RecordingUploadStatusUpdateRequest(
        @NotNull UploadStatus uploadStatus,
        @PositiveOrZero Long fileSize) {
}
