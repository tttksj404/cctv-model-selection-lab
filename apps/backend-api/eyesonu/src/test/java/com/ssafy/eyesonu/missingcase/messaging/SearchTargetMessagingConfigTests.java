package com.ssafy.eyesonu.missingcase.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import org.springframework.amqp.core.Binding;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;

class SearchTargetMessagingConfigTests {

    private final SearchTargetMessagingConfig configuration = new SearchTargetMessagingConfig();

    @Test
    void retryQueuesUseFixedTtlBucketsWithoutPerMessageHeadOfLineBlocking() {
        TopicExchange retryExchange = configuration.recordingAnalysisRetryExchange();

        assertThat(retryExchange.getName()).isEqualTo(RecordingAnalysisJobPublisher.RETRY_EXCHANGE);
        assertRetryQueue(configuration.recordingAnalysisRetry5SecondsQueue(), 5_000);
        assertRetryQueue(configuration.recordingAnalysisRetry15SecondsQueue(), 15_000);
        assertRetryQueue(configuration.recordingAnalysisRetry30SecondsQueue(), 30_000);
        assertRetryQueue(configuration.recordingAnalysisRetry60SecondsQueue(), 60_000);
        assertRetryQueue(configuration.recordingAnalysisRetry300SecondsQueue(), 300_000);
        Binding retry60Binding = configuration.recordingAnalysisRetry60SecondsBinding(
                configuration.recordingAnalysisRetry60SecondsQueue(), retryExchange);
        assertThat(retry60Binding.getRoutingKey())
                .isEqualTo(RecordingAnalysisJobPublisher.retryRoutingKey(60));
    }

    private void assertRetryQueue(Queue retryQueue, int ttlMillis) {
        assertThat(retryQueue.getArguments())
                .containsEntry("x-dead-letter-exchange", RecordingAnalysisJobPublisher.EXCHANGE)
                .containsEntry("x-dead-letter-routing-key", RecordingAnalysisJobPublisher.ROUTING_KEY)
                .containsEntry("x-message-ttl", ttlMillis);
    }
}
