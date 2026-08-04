package com.ssafy.eyesonu.recording.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import java.time.Duration;
import java.util.List;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "recording.analysis")
public class RecordingAnalysisProperties {

    private static final List<Integer> DEFAULT_RETRY_DELAY_BUCKETS_SECONDS =
            List.of(5, 15, 30, 60, 300);

    @Positive
    private long workerClaimLeaseSeconds = 300;

    @Valid
    private final Outbox outbox = new Outbox();

    @Valid
    private final LeaseRecovery leaseRecovery = new LeaseRecovery();

    @Valid
    private final BackendConsumer backendConsumer = new BackendConsumer();

    @NotEmpty
    private List<@Positive Integer> retryDelayBucketsSeconds = DEFAULT_RETRY_DELAY_BUCKETS_SECONDS;

    public long getWorkerClaimLeaseSeconds() {
        return workerClaimLeaseSeconds;
    }

    public void setWorkerClaimLeaseSeconds(long workerClaimLeaseSeconds) {
        this.workerClaimLeaseSeconds = workerClaimLeaseSeconds;
    }

    public Outbox getOutbox() {
        return outbox;
    }

    public LeaseRecovery getLeaseRecovery() {
        return leaseRecovery;
    }

    public BackendConsumer getBackendConsumer() {
        return backendConsumer;
    }

    public List<Integer> getRetryDelayBucketsSeconds() {
        return List.copyOf(retryDelayBucketsSeconds);
    }

    public void setRetryDelayBucketsSeconds(List<Integer> retryDelayBucketsSeconds) {
        this.retryDelayBucketsSeconds = List.copyOf(retryDelayBucketsSeconds);
    }

    @AssertTrue(message = "Recording analysis retry delay buckets must be positive and strictly ascending")
    public boolean isRetryDelayBucketsStrictlyAscending() {
        if (retryDelayBucketsSeconds == null || retryDelayBucketsSeconds.isEmpty()) {
            return false;
        }
        int previousBucket = 0;
        for (Integer bucket : retryDelayBucketsSeconds) {
            if (bucket == null || bucket <= previousBucket) {
                return false;
            }
            previousBucket = bucket;
        }
        return true;
    }

    public static class Outbox {

        @Positive
        private long claimLeaseSeconds = 300;

        @Positive
        private int publishBatchSize = 50;

        @NotNull
        private Duration confirmTimeout = Duration.ofSeconds(5);

        @NotNull
        private Duration confirmPollInterval = Duration.ofMillis(200);

        public long getClaimLeaseSeconds() {
            return claimLeaseSeconds;
        }

        public void setClaimLeaseSeconds(long claimLeaseSeconds) {
            this.claimLeaseSeconds = claimLeaseSeconds;
        }

        public int getPublishBatchSize() {
            return publishBatchSize;
        }

        public void setPublishBatchSize(int publishBatchSize) {
            this.publishBatchSize = publishBatchSize;
        }

        public Duration getConfirmTimeout() {
            return confirmTimeout;
        }

        public void setConfirmTimeout(Duration confirmTimeout) {
            this.confirmTimeout = confirmTimeout;
        }

        public Duration getConfirmPollInterval() {
            return confirmPollInterval;
        }

        public void setConfirmPollInterval(Duration confirmPollInterval) {
            this.confirmPollInterval = confirmPollInterval;
        }

        @AssertTrue(message = "Outbox confirm timings must be positive and poll no slower than timeout")
        public boolean isConfirmPollingValid() {
            return isPositive(confirmTimeout)
                    && isPositive(confirmPollInterval)
                    && confirmPollInterval.compareTo(confirmTimeout) <= 0;
        }

        private boolean isPositive(Duration duration) {
            return duration != null && !duration.isZero() && !duration.isNegative();
        }
    }

    public static class LeaseRecovery {

        @Positive
        private int batchSize = 50;

        public int getBatchSize() {
            return batchSize;
        }

        public void setBatchSize(int batchSize) {
            this.batchSize = batchSize;
        }
    }

    public static class BackendConsumer {

        @NotBlank
        private String queue = "recording.analysis.backend.queue";

        @Valid
        private final Retry retry = new Retry();

        public String getQueue() {
            return queue;
        }

        public void setQueue(String queue) {
            this.queue = queue;
        }

        public Retry getRetry() {
            return retry;
        }

        public static class Retry {

            @Positive
            private int maxAttempts = 2;

            @Positive
            private long initialIntervalMs = 1_000;

            @DecimalMin(value = "1.0")
            private double multiplier = 2.0;

            @Positive
            private long maxIntervalMs = 10_000;

            public int getMaxAttempts() {
                return maxAttempts;
            }

            public void setMaxAttempts(int maxAttempts) {
                this.maxAttempts = maxAttempts;
            }

            public long getInitialIntervalMs() {
                return initialIntervalMs;
            }

            public void setInitialIntervalMs(long initialIntervalMs) {
                this.initialIntervalMs = initialIntervalMs;
            }

            public double getMultiplier() {
                return multiplier;
            }

            public void setMultiplier(double multiplier) {
                this.multiplier = multiplier;
            }

            public long getMaxIntervalMs() {
                return maxIntervalMs;
            }

            public void setMaxIntervalMs(long maxIntervalMs) {
                this.maxIntervalMs = maxIntervalMs;
            }

            @AssertTrue(message = "Backend consumer retry max interval must be no smaller than initial interval")
            public boolean isIntervalRangeValid() {
                return maxIntervalMs >= initialIntervalMs;
            }
        }
    }
}
