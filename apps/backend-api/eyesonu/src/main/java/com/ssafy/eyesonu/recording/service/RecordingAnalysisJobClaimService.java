package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.util.Optional;
import com.ssafy.eyesonu.common.exception.ApiException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.beans.factory.annotation.Value;

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
    private static final String BACKEND_WORKER_ID = "backend-rabbit-consumer";

    private final AnalysisJobMapper analysisJobMapper;
    private final long claimLeaseSeconds;

    public RecordingAnalysisJobClaimService(
            AnalysisJobMapper analysisJobMapper,
            @Value("${recording.analysis.worker-claim-lease-seconds:300}") long claimLeaseSeconds) {
        this.analysisJobMapper = analysisJobMapper;
        this.claimLeaseSeconds = claimLeaseSeconds;
    }

    @Transactional
    public Optional<AnalysisJob> claim(Long jobId) {
        if (analysisJobMapper.claimQueued(jobId, BACKEND_WORKER_ID, claimLeaseSeconds) != 1) {
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

    @Transactional
    public RecordingAnalysisJobClaimResult claimForWorker(Long jobId, String workerId) {
        if (workerId == null || workerId.isBlank()) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED",
                    "Authenticated worker is required.");
        }
        if (analysisJobMapper.claimQueued(jobId, workerId, claimLeaseSeconds) == 1) {
            AnalysisJob claimed = requireJob(jobId);
            return new RecordingAnalysisJobClaimResult(claimed, false);
        }

        AnalysisJob current = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (current == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        if (RUNNING.equals(current.getStatus())) {
            return new RecordingAnalysisJobClaimResult(current, true);
        }
        throw new ApiException(HttpStatus.CONFLICT, "JOB_NOT_RUNNABLE",
                "Recording analysis job cannot be claimed from status " + current.getStatus() + ".");
    }

    private AnalysisJob requireJob(Long jobId) {
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null || !RUNNING.equals(job.getStatus())) {
            throw new IllegalStateException("Claimed recording analysis job could not be reloaded: " + jobId);
        }
        return job;
    }
}
