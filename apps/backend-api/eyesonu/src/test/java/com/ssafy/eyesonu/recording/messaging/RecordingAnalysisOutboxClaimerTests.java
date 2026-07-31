package com.ssafy.eyesonu.recording.messaging;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.ArgumentCaptor;
import org.mockito.junit.jupiter.MockitoExtension;

@ExtendWith(MockitoExtension.class)
class RecordingAnalysisOutboxClaimerTests {

    @Mock
    private RecordingAnalysisOutboxMapper outboxMapper;

    @Test
    void returnsEmptyWhenNoOutboxIsReady() {
        when(outboxMapper.findReady(1)).thenReturn(List.of());

        Optional<ClaimedRecordingAnalysisOutbox> claimed =
                new RecordingAnalysisOutboxClaimer(outboxMapper, 300).claimNext();

        assertTrue(claimed.isEmpty());
        verify(outboxMapper, never()).markProcessing(
                org.mockito.ArgumentMatchers.any(), anyString(), org.mockito.ArgumentMatchers.any());
    }

    @Test
    void marksSelectedOutboxProcessingBeforeReturningIt() {
        RecordingAnalysisOutbox outbox = readyOutbox();
        when(outboxMapper.findReady(1)).thenReturn(List.of(outbox));
        when(outboxMapper.markProcessing(
                org.mockito.ArgumentMatchers.eq(1L), anyString(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(1);

        ClaimedRecordingAnalysisOutbox claimed =
                new RecordingAnalysisOutboxClaimer(outboxMapper, 300).claimNext().orElseThrow();

        assertEquals(outbox, claimed.outbox());
        ArgumentCaptor<Instant> leaseCaptor = ArgumentCaptor.forClass(Instant.class);
        verify(outboxMapper).markProcessing(
                eq(1L), eq(claimed.claimToken()), leaseCaptor.capture());
        assertTrue(leaseCaptor.getValue().isAfter(Instant.now().plusSeconds(299)));
    }

    @Test
    void failsWhenSelectedOutboxCannotBeClaimed() {
        when(outboxMapper.findReady(1)).thenReturn(List.of(readyOutbox()));
        when(outboxMapper.markProcessing(
                org.mockito.ArgumentMatchers.eq(1L), anyString(), org.mockito.ArgumentMatchers.any()))
                .thenReturn(0);

        assertThrows(IllegalStateException.class,
                () -> new RecordingAnalysisOutboxClaimer(outboxMapper, 300).claimNext());
    }

    private RecordingAnalysisOutbox readyOutbox() {
        return new RecordingAnalysisOutbox(
                1L, "cmd-1", RecordingAnalysisJobPublisher.EVENT_TYPE,
                5001L, 101L, Instant.parse("2026-07-31T04:00:00Z"), 0);
    }
}
