package com.ssafy.eyesonu.recording.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

class RecordingAnalysisOutboxSchedulerTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(RecordingAnalysisOutboxScheduler.class)
            .withBean(RecordingAnalysisJobPublisher.class, () -> mock(RecordingAnalysisJobPublisher.class));

    @Test
    void doesNotRegisterSchedulerWhenOutboxAutoStartIsDisabled() {
        contextRunner
                .withPropertyValues("recording.analysis.outbox.auto-start=false")
                .run(context -> assertThat(context).doesNotHaveBean(RecordingAnalysisOutboxScheduler.class));
    }

    @Test
    void delegatesPollingWhenOutboxAutoStartIsEnabled() {
        contextRunner
                .withPropertyValues("recording.analysis.outbox.auto-start=true")
                .run(context -> {
                    RecordingAnalysisJobPublisher publisher =
                            context.getBean(RecordingAnalysisJobPublisher.class);
                    context.getBean(RecordingAnalysisOutboxScheduler.class).publishPending();

                    verify(publisher).publishPending();
                });
    }
}
