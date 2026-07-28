package com.ssafy.eyesonu.recording.dto.admin;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.time.LocalDateTime;

public record AdminRecordingResponse(Long id, Long cameraId, LocalDateTime startTime,
        LocalDateTime endTime, Long fileSize, UploadStatus uploadStatus, LocalDateTime createdAt) {
    public static AdminRecordingResponse from(Recording recording) {
        return new AdminRecordingResponse(recording.getId(), recording.getCameraId(), recording.getStartTime(),
                recording.getEndTime(), recording.getFileSize(), recording.getUploadStatus(), recording.getCreatedAt());
    }
}
