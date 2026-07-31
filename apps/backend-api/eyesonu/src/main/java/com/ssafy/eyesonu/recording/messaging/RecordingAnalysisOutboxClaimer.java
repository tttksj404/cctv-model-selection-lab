package com.ssafy.eyesonu.recording.messaging;

import com.ssafy.eyesonu.recording.domain.RecordingAnalysisOutbox;
import com.ssafy.eyesonu.recording.mapper.RecordingAnalysisOutboxMapper;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.transaction.annotation.Transactional;

@Component
public class RecordingAnalysisOutboxClaimer {

    private final RecordingAnalysisOutboxMapper outboxMapper;
    private final long claimLeaseSeconds;

    public RecordingAnalysisOutboxClaimer(
            RecordingAnalysisOutboxMapper outboxMapper,
            @Value("${recording.analysis.outbox.claim-lease-seconds:300}") long claimLeaseSeconds) {
        this.outboxMapper = outboxMapper;
        this.claimLeaseSeconds = claimLeaseSeconds;
    }

    @Transactional
    public Optional<ClaimedRecordingAnalysisOutbox> claimNext() {
        List<RecordingAnalysisOutbox> ready = outboxMapper.findReady(1);
        if (ready.isEmpty()) {
            return Optional.empty();
        }

        RecordingAnalysisOutbox outbox = ready.getFirst();
        String claimToken = UUID.randomUUID().toString();
        Instant leaseUntil = Instant.now().plusSeconds(claimLeaseSeconds);
        int claimed = outboxMapper.markProcessing(outbox.getId(), claimToken, leaseUntil);
        if (claimed != 1) {
            throw new IllegalStateException("Failed to claim recording analysis outbox: " + outbox.getId());
        }
        return Optional.of(new ClaimedRecordingAnalysisOutbox(outbox, claimToken));
    }
}
