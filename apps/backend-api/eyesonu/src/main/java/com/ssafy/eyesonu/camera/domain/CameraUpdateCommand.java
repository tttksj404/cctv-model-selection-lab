package com.ssafy.eyesonu.camera.domain;

import java.math.BigDecimal;

public record CameraUpdateCommand(
        Long cameraId,
        Long mediaServerId,
        String cameraName,
        BigDecimal latitude,
        BigDecimal longitude,
        String address,
        String rtspUrl) {
}
