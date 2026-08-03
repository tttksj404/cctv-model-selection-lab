package com.ssafy.eyesonu.camera.service;

import java.time.Duration;
import java.time.Instant;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

@Component
public class CameraOfflineStatusScheduler {

    private final CameraHeartbeatService heartbeatService;
    private final Duration offlineTimeout;

    public CameraOfflineStatusScheduler(
            CameraHeartbeatService heartbeatService,
            CameraHeartbeatProperties properties) {
        this.heartbeatService = heartbeatService;
        this.offlineTimeout = properties.getOfflineTimeout();
    }

    @Scheduled(fixedDelayString = "${camera.heartbeat.status-check-interval-ms:10000}")
    public void markTimedOutCamerasOffline() {
        heartbeatService.markOffline(Instant.now(), offlineTimeout);
    }
}
