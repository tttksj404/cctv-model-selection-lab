package com.ssafy.eyesonu.recording.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

class RecordingAnalysisJobListenerTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(RecordingAnalysisJobListener.class)
            .withBean(RecordingAnalysisJobConsumer.class, () -> mock(RecordingAnalysisJobConsumer.class));

    @Test
    void doesNotRegisterRabbitListenerWhenConsumerAutoStartIsDisabled() {
        contextRunner
                .withPropertyValues("recording.analysis.backend-consumer.auto-start=false")
                .run(context -> assertThat(context).doesNotHaveBean(RecordingAnalysisJobListener.class));
    }

    @Test
    void delegatesMessageToConsumerWhenEnabled() {
        contextRunner
                .withPropertyValues("recording.analysis.backend-consumer.auto-start=true")
                .run(context -> {
                    RecordingAnalysisJobConsumer consumer =
                            context.getBean(RecordingAnalysisJobConsumer.class);
                    RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                            "command-1", RecordingAnalysisJobPublisher.EVENT_TYPE, 5001L, Instant.now());

                    context.getBean(RecordingAnalysisJobListener.class).consume(event);

                    verify(consumer).consume(event);
                });
    }
}
