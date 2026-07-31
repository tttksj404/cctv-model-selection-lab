package com.ssafy.eyesonu.recording.messaging;

import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimService;
import java.time.Instant;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisJobConsumerTests {

    @Mock
    private RecordingAnalysisJobClaimService claimService;

    @Test
    void claimsJobReceivedFromRabbitMq() {
        RecordingAnalysisJobConsumer consumer = new RecordingAnalysisJobConsumer(claimService);
        RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                "command-1", RecordingAnalysisJobPublisher.EVENT_TYPE, 5001L, 101L, Instant.now());

        consumer.consume(event);

        verify(claimService).claim(5001L);
    }

    @Test
    void acknowledgesMalformedEventWithoutRetrying() {
        RecordingAnalysisJobConsumer consumer = new RecordingAnalysisJobConsumer(claimService);
        RecordingAnalysisJobEvent event = new RecordingAnalysisJobEvent(
                "command-1", RecordingAnalysisJobPublisher.EVENT_TYPE, null, 101L, Instant.now());

        consumer.consume(event);

        verify(claimService, never()).claim(org.mockito.ArgumentMatchers.anyLong());
    }
}
