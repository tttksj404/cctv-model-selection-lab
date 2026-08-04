package com.ssafy.eyesonu.camera.service;

import jakarta.validation.constraints.AssertTrue;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "camera.heartbeat")
public class CameraHeartbeatProperties {

    private long offlineTimeoutMs = 30_000;

    private long statusCheckIntervalMs = 10_000;

    public java.time.Duration getOfflineTimeout() {
        return java.time.Duration.ofMillis(offlineTimeoutMs);
    }

    public long getOfflineTimeoutMs() {
        return offlineTimeoutMs;
    }

    public void setOfflineTimeoutMs(long offlineTimeoutMs) {
        this.offlineTimeoutMs = offlineTimeoutMs;
    }

    public long getStatusCheckIntervalMs() {
        return statusCheckIntervalMs;
    }

    public void setStatusCheckIntervalMs(long statusCheckIntervalMs) {
        this.statusCheckIntervalMs = statusCheckIntervalMs;
    }

    @AssertTrue(message = "camera heartbeat timeout and status check interval must be positive")
    public boolean isTimingConfigurationValid() {
        return offlineTimeoutMs > 0 && statusCheckIntervalMs > 0;
    }
}
