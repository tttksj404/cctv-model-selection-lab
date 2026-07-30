package com.ssafy.eyesonu.camera.dto;

import com.ssafy.eyesonu.camera.domain.CameraManagementRow;
import java.math.BigDecimal;
import java.time.Instant;

public record CameraListResponse(
        Long id,
        String cameraCode,
        String cameraName,
        MediaServerSummaryResponse mediaServer,
        BigDecimal latitude,
        BigDecimal longitude,
        String address,
        String status,
        Instant lastHeartbeat,
        Instant createdAt,
        Instant updatedAt) {

    public static CameraListResponse from(CameraManagementRow row) {
        return new CameraListResponse(
                row.id(),
                row.cameraCode(),
                row.cameraName(),
                MediaServerSummaryResponse.from(row),
                row.latitude(),
                row.longitude(),
                row.address(),
                row.status(),
                row.lastHeartbeat(),
                row.createdAt(),
                row.updatedAt());
    }
}
