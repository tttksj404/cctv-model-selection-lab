package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.domain.UploadStatus;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.PositiveOrZero;

public record UploadStatusUpdateRequest(@NotNull UploadStatus uploadStatus, @PositiveOrZero Long fileSize) {
}
