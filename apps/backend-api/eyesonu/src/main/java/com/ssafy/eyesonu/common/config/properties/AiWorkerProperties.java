package com.ssafy.eyesonu.common.config.properties;

import java.time.Duration;
import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "eyesonu.ai-worker")
public class AiWorkerProperties {

    private String apiKey = "";
    private Duration leaseDuration = Duration.ofSeconds(90);
    private int maxRetryCount = 3;
    private int maxResultBytes = 8 * 1024 * 1024;
    private int emptyPollAfterMs = 1000;

    public String getApiKey() {
        return apiKey;
    }

    public void setApiKey(String apiKey) {
        this.apiKey = apiKey;
    }

    public Duration getLeaseDuration() {
        return leaseDuration;
    }

    public void setLeaseDuration(Duration leaseDuration) {
        this.leaseDuration = leaseDuration;
    }

    public int getMaxRetryCount() {
        return maxRetryCount;
    }

    public void setMaxRetryCount(int maxRetryCount) {
        this.maxRetryCount = maxRetryCount;
    }

    public int getMaxResultBytes() {
        return maxResultBytes;
    }

    public void setMaxResultBytes(int maxResultBytes) {
        this.maxResultBytes = maxResultBytes;
    }

    public int getEmptyPollAfterMs() {
        return emptyPollAfterMs;
    }

    public void setEmptyPollAfterMs(int emptyPollAfterMs) {
        this.emptyPollAfterMs = emptyPollAfterMs;
    }
}
