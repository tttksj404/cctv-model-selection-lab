package com.ssafy.eyesonu.camera.domain;

import java.math.BigDecimal;
import java.time.Instant;

public record CameraManagementRow(
        Long id,
        Long mediaServerId,
        String mediaServerCode,
        String mediaServerName,
        String cameraCode,
        String cameraName,
        BigDecimal latitude,
        BigDecimal longitude,
        String address,
        String rtspUrl,
        String status,
        Instant lastHeartbeat,
        Instant createdAt,
        Instant updatedAt) {
}
