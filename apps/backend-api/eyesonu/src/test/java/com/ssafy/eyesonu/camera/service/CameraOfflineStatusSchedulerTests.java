package com.ssafy.eyesonu.camera.service;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.time.Duration;
import java.time.Instant;
import org.junit.jupiter.api.Test;

class CameraOfflineStatusSchedulerTests {

    @Test
    void passesConfiguredOfflineTimeoutToStatusCheck() {
        CameraHeartbeatService heartbeatService = mock(CameraHeartbeatService.class);
        CameraHeartbeatProperties properties = new CameraHeartbeatProperties();
        properties.setOfflineTimeoutMs(45_000);
        properties.setStatusCheckIntervalMs(5_000);

        CameraOfflineStatusScheduler scheduler =
                new CameraOfflineStatusScheduler(heartbeatService, properties);

        scheduler.markTimedOutCamerasOffline();

        verify(heartbeatService).markOffline(any(Instant.class), eq(Duration.ofSeconds(45)));
    }
}
