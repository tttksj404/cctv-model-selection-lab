package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.domain.Recording;
import java.time.Instant;

public record RecordingCreateResponse(
        Long id,
        Long cameraId,
        Instant startTime,
        Instant endTime,
        Long fileSize,
        boolean duplicate,
        Instant createdAt) {

    public static RecordingCreateResponse from(Recording recording, boolean duplicate) {
        return new RecordingCreateResponse(recording.getId(), recording.getCameraId(), recording.getStartTime(),
                recording.getEndTime(), recording.getFileSize(), duplicate, recording.getCreatedAt());
    }
}
