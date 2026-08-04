package com.ssafy.eyesonu.recording.messaging;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobLeaseRecoveryService;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;

class RecordingAnalysisJobLeaseRecoverySchedulerTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(RecordingAnalysisJobLeaseRecoveryScheduler.class)
            .withBean(RecordingAnalysisJobLeaseRecoveryService.class,
                    () -> mock(RecordingAnalysisJobLeaseRecoveryService.class));

    @Test
    void doesNotRegisterSchedulerWhenLeaseRecoveryIsDisabled() {
        contextRunner
                .withPropertyValues("recording.analysis.lease-recovery.auto-start=false")
                .run(context -> assertThat(context)
                        .doesNotHaveBean(RecordingAnalysisJobLeaseRecoveryScheduler.class));
    }

    @Test
    void delegatesLeaseRecoveryWhenEnabled() {
        contextRunner
                .withPropertyValues("recording.analysis.lease-recovery.auto-start=true")
                .run(context -> {
                    RecordingAnalysisJobLeaseRecoveryService service =
                            context.getBean(RecordingAnalysisJobLeaseRecoveryService.class);
                    context.getBean(RecordingAnalysisJobLeaseRecoveryScheduler.class)
                            .recoverExpiredJobs();

                    verify(service).recoverExpiredJobs();
                });
    }
}
