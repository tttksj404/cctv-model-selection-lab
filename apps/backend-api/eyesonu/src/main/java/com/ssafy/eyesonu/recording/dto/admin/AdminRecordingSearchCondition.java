package com.ssafy.eyesonu.recording.dto.admin;

import com.ssafy.eyesonu.recording.domain.UploadStatus;
import java.time.LocalDateTime;

public record AdminRecordingSearchCondition(Long cameraId, UploadStatus uploadStatus,
        LocalDateTime startFrom, LocalDateTime startTo) {
}
