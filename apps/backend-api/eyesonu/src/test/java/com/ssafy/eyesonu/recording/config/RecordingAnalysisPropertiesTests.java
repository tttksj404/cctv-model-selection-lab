package com.ssafy.eyesonu.recording.config;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.context.annotation.Configuration;

class RecordingAnalysisPropertiesTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(RecordingAnalysisPropertiesConfiguration.class);

    @Test
    void bindsLeaseRetryAndPublisherTuningFromOneConfigurationBoundary() {
        contextRunner
                .withPropertyValues(
                        "recording.analysis.worker-claim-lease-seconds=123",
                        "recording.analysis.retry-delay-buckets-seconds[0]=7",
                        "recording.analysis.retry-delay-buckets-seconds[1]=11",
                        "recording.analysis.outbox.claim-lease-seconds=45",
                        "recording.analysis.outbox.publish-batch-size=9",
                        "recording.analysis.outbox.confirm-timeout=8s",
                        "recording.analysis.outbox.confirm-poll-interval=250ms",
                        "recording.analysis.lease-recovery.batch-size=6",
                        "recording.analysis.backend-consumer.queue=recording.analysis.recovery.queue",
                        "recording.analysis.backend-consumer.retry.max-attempts=4",
                        "recording.analysis.backend-consumer.retry.initial-interval-ms=125",
                        "recording.analysis.backend-consumer.retry.multiplier=1.5",
                        "recording.analysis.backend-consumer.retry.max-interval-ms=900")
                .run(context -> {
                    RecordingAnalysisProperties properties = context.getBean(RecordingAnalysisProperties.class);

                    assertThat(properties.getWorkerClaimLeaseSeconds()).isEqualTo(123);
                    assertThat(properties.getRetryDelayBucketsSeconds()).containsExactly(7, 11);
                    assertThat(properties.getOutbox().getClaimLeaseSeconds()).isEqualTo(45);
                    assertThat(properties.getOutbox().getPublishBatchSize()).isEqualTo(9);
                    assertThat(properties.getOutbox().getConfirmTimeout()).isEqualTo(Duration.ofSeconds(8));
                    assertThat(properties.getOutbox().getConfirmPollInterval())
                            .isEqualTo(Duration.ofMillis(250));
                    assertThat(properties.getLeaseRecovery().getBatchSize()).isEqualTo(6);
                    assertThat(properties.getBackendConsumer().getQueue())
                            .isEqualTo("recording.analysis.recovery.queue");
                    assertThat(properties.getBackendConsumer().getRetry().getMaxAttempts()).isEqualTo(4);
                    assertThat(properties.getBackendConsumer().getRetry().getInitialIntervalMs())
                            .isEqualTo(125);
                    assertThat(properties.getBackendConsumer().getRetry().getMultiplier())
                            .isEqualTo(1.5);
                    assertThat(properties.getBackendConsumer().getRetry().getMaxIntervalMs())
                            .isEqualTo(900);
                });
    }

    @Configuration(proxyBeanMethods = false)
    @EnableConfigurationProperties(RecordingAnalysisProperties.class)
    static class RecordingAnalysisPropertiesConfiguration {
    }
}
