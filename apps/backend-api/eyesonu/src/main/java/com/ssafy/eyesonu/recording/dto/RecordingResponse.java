package com.ssafy.eyesonu.recording.dto;

import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.time.LocalDateTime;

public record RecordingResponse(
        Long id,
        Long cameraId,
        LocalDateTime startTime,
        LocalDateTime endTime,
        Long fileSize,
        UploadStatus uploadStatus,
        LocalDateTime createdAt) {

    public static RecordingResponse from(Recording recording) {
        return new RecordingResponse(recording.getId(), recording.getCameraId(), recording.getStartTime(),
                recording.getEndTime(), recording.getFileSize(), recording.getUploadStatus(), recording.getCreatedAt());
    }
}
