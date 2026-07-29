package com.ssafy.eyesonu.recording.dto.admin;

import java.time.OffsetDateTime;

public record AdminRecordingSearchCondition(
        Long cameraId,
        OffsetDateTime startFrom,
        OffsetDateTime startTo,
        int page,
        int size,
        String sort) {
}
