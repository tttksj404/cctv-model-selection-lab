package com.ssafy.eyesonu.recording.dto.admin;

import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import java.time.Instant;

public record AdminRecordingDetailResponse(
        Long id,
        AdminRecordingCameraResponse camera,
        Instant startTime,
        Instant endTime,
        Long fileSize,
        String videoUrl,
        Instant createdAt) {

    public static AdminRecordingDetailResponse from(AdminRecordingRow row, String videoUrl) {
        return new AdminRecordingDetailResponse(
                row.getId(),
                new AdminRecordingCameraResponse(row.getCameraId(), row.getCameraCode(), row.getCameraName()),
                row.getStartTime(),
                row.getEndTime(),
                row.getFileSize(),
                videoUrl,
                row.getCreatedAt());
    }
}
