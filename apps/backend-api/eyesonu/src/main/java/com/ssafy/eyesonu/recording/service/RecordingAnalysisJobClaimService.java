package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.util.Optional;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Claims recording-analysis jobs for a worker.
 *
 * <p>The status predicate is part of the UPDATE so concurrent workers cannot
 * claim the same queued job. A second delivery of the same RabbitMQ message
 * therefore returns an empty result and can be acknowledged safely.</p>
 */
@Service
public class RecordingAnalysisJobClaimService {

    private static final String RECORDING_ANALYSIS = "RECORDING_ANALYSIS";
    private static final String RUNNING = "RUNNING";

    private final AnalysisJobMapper analysisJobMapper;

    public RecordingAnalysisJobClaimService(AnalysisJobMapper analysisJobMapper) {
        this.analysisJobMapper = analysisJobMapper;
    }

    @Transactional
    public Optional<AnalysisJob> claim(Long jobId) {
        if (analysisJobMapper.claimQueued(jobId) != 1) {
            return Optional.empty();
        }

        AnalysisJob claimed = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (claimed == null
                || !RECORDING_ANALYSIS.equals(claimed.getJobType())
                || !RUNNING.equals(claimed.getStatus())) {
            throw new IllegalStateException("Claimed recording analysis job could not be reloaded: " + jobId);
        }
        return Optional.of(claimed);
    }
}
