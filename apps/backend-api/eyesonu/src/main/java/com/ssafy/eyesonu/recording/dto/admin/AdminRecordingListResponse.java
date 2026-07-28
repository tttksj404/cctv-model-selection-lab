package com.ssafy.eyesonu.recording.dto.admin;

import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import java.time.Instant;

public record AdminRecordingListResponse(
        Long id,
        AdminRecordingCameraResponse camera,
        Instant startTime,
        Instant endTime,
        Long fileSize,
        Instant createdAt) {

    public static AdminRecordingListResponse from(AdminRecordingRow row) {
        return new AdminRecordingListResponse(
                row.getId(),
                new AdminRecordingCameraResponse(row.getCameraId(), row.getCameraCode(), row.getCameraName()),
                row.getStartTime(),
                row.getEndTime(),
                row.getFileSize(),
                row.getCreatedAt());
    }
}
