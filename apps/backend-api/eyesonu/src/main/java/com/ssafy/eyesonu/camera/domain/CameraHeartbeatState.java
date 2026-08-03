package com.ssafy.eyesonu.camera.domain;

import java.time.Instant;

public record CameraHeartbeatState(
        Long id,
        Long mediaServerId,
        String cameraCode,
        String status,
        Instant lastHeartbeat) {
}
