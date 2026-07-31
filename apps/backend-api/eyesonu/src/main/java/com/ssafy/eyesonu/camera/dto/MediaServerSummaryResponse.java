package com.ssafy.eyesonu.camera.dto;

import com.ssafy.eyesonu.camera.domain.CameraManagementRow;

public record MediaServerSummaryResponse(
        Long id,
        String serverCode,
        String name) {

    public static MediaServerSummaryResponse from(CameraManagementRow row) {
        return new MediaServerSummaryResponse(row.mediaServerId(), row.mediaServerCode(), row.mediaServerName());
    }
}
