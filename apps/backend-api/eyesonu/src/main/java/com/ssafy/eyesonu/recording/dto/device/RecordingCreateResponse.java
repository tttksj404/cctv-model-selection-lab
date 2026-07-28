package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.time.LocalDateTime;

public record RecordingCreateResponse(Long id, Long cameraId, LocalDateTime startTime,
        LocalDateTime endTime, Long fileSize, UploadStatus uploadStatus, LocalDateTime createdAt) {
    public static RecordingCreateResponse from(Recording recording) {
        return new RecordingCreateResponse(recording.getId(), recording.getCameraId(), recording.getStartTime(),
                recording.getEndTime(), recording.getFileSize(), recording.getUploadStatus(), recording.getCreatedAt());
    }
}
