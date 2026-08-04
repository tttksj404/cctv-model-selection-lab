package com.ssafy.eyesonu.missingcase.messaging;

import static org.assertj.core.api.Assertions.assertThat;

import com.ssafy.eyesonu.recording.config.RecordingAnalysisProperties;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import java.util.List;
import org.springframework.amqp.core.Binding;
import org.springframework.amqp.core.Declarables;
import org.junit.jupiter.api.Test;
import org.springframework.amqp.core.Queue;
import org.springframework.amqp.core.TopicExchange;

class SearchTargetMessagingConfigTests {

    private final SearchTargetMessagingConfig configuration = new SearchTargetMessagingConfig();

    @Test
    void retryTopologyUsesConfiguredTtlBucketsWithoutPerMessageHeadOfLineBlocking() {
        TopicExchange retryExchange = configuration.recordingAnalysisRetryExchange();
        RecordingAnalysisProperties properties = new RecordingAnalysisProperties();
        properties.setRetryDelayBucketsSeconds(List.of(5, 15, 30, 60, 300));
        Declarables retryTopology = configuration.recordingAnalysisRetryTopology(retryExchange, properties);

        assertThat(retryExchange.getName()).isEqualTo(RecordingAnalysisJobPublisher.RETRY_EXCHANGE);
        assertRetryQueue(retryQueue(retryTopology, 5), 5_000);
        assertRetryQueue(retryQueue(retryTopology, 15), 15_000);
        assertRetryQueue(retryQueue(retryTopology, 30), 30_000);
        assertRetryQueue(retryQueue(retryTopology, 60), 60_000);
        assertRetryQueue(retryQueue(retryTopology, 300), 300_000);
        Binding retry60Binding = retryBinding(retryTopology, 60);
        assertThat(retry60Binding.getRoutingKey())
                .isEqualTo(RecordingAnalysisJobPublisher.retryRoutingKey(60));
    }

    @Test
    void retryTopologyUsesTheConfiguredBucketList() {
        TopicExchange retryExchange = configuration.recordingAnalysisRetryExchange();
        RecordingAnalysisProperties properties = new RecordingAnalysisProperties();
        properties.setRetryDelayBucketsSeconds(List.of(7, 11));

        Declarables retryTopology = configuration.recordingAnalysisRetryTopology(retryExchange, properties);

        assertThat(retryTopology.getDeclarables().stream()
                .filter(Queue.class::isInstance)
                .map(Queue.class::cast)
                .map(Queue::getName))
                .containsExactlyInAnyOrder(
                        RecordingAnalysisJobPublisher.retryQueueName(7),
                        RecordingAnalysisJobPublisher.retryQueueName(11));
        assertThat(retryBinding(retryTopology, 11).getRoutingKey())
                .isEqualTo(RecordingAnalysisJobPublisher.retryRoutingKey(11));
    }

    private void assertRetryQueue(Queue retryQueue, int ttlMillis) {
        assertThat(retryQueue.getArguments())
                .containsEntry("x-dead-letter-exchange", RecordingAnalysisJobPublisher.EXCHANGE)
                .containsEntry("x-dead-letter-routing-key", RecordingAnalysisJobPublisher.ROUTING_KEY)
                .containsEntry("x-message-ttl", ttlMillis);
    }

    private Queue retryQueue(Declarables retryTopology, int delaySeconds) {
        return retryTopology.getDeclarables().stream()
                .filter(Queue.class::isInstance)
                .map(Queue.class::cast)
                .filter(queue -> queue.getName().equals(RecordingAnalysisJobPublisher.retryQueueName(delaySeconds)))
                .findFirst()
                .orElseThrow();
    }

    private Binding retryBinding(Declarables retryTopology, int delaySeconds) {
        return retryTopology.getDeclarables().stream()
                .filter(Binding.class::isInstance)
                .map(Binding.class::cast)
                .filter(binding -> binding.getRoutingKey()
                        .equals(RecordingAnalysisJobPublisher.retryRoutingKey(delaySeconds)))
                .findFirst()
                .orElseThrow();
    }
}
