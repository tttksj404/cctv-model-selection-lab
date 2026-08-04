package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.config.RecordingAnalysisProperties;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Instant;
import java.util.Optional;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

/**
 * Claims recording-analysis jobs for a worker.
 *
 * <p>The status predicate is part of the UPDATE so concurrent workers cannot
 * claim the same queued job. A second delivery returns an explicit disposition:
 * the worker must defer while its own or another worker's active lease is held, retry shortly if a
 * concurrent administrative retry made the job queued again, and acknowledge a
 * terminal job as stale.</p>
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
            RecordingAnalysisProperties properties) {
        this.analysisJobMapper = analysisJobMapper;
        this.claimLeaseSeconds = properties.getWorkerClaimLeaseSeconds();
    }

    @Transactional
    public Optional<AnalysisJob> claim(Long jobId) {
        String leaseTokenHash = hashClaimToken(UUID.randomUUID().toString());
        if (analysisJobMapper.claimQueued(
                jobId, BACKEND_WORKER_ID, leaseTokenHash, claimLeaseSeconds) != 1) {
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
        requireWorkerId(workerId);
        String leaseToken = UUID.randomUUID().toString();
        if (analysisJobMapper.claimQueued(
                jobId, workerId, hashClaimToken(leaseToken), claimLeaseSeconds) == 1) {
            AnalysisJob claimed = requireJob(jobId);
            return new RecordingAnalysisJobClaimResult(
                    claimed, RecordingAnalysisClaimDisposition.CLAIMED, leaseToken);
        }

        AnalysisJob current = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (current == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        if (RUNNING.equals(current.getStatus())) {
            populateLegacyLeaseExpiry(current);
            RecordingAnalysisClaimDisposition disposition = workerId.equals(current.getClaimedBy())
                    ? RecordingAnalysisClaimDisposition.LEASE_HELD_BY_SELF
                    : RecordingAnalysisClaimDisposition.LEASE_HELD_BY_OTHER;
            return new RecordingAnalysisJobClaimResult(
                    current, disposition, null);
        }
        if ("QUEUED".equals(current.getStatus())) {
            return new RecordingAnalysisJobClaimResult(
                    current, RecordingAnalysisClaimDisposition.RETRY_PENDING, null);
        }
        return new RecordingAnalysisJobClaimResult(
                current, RecordingAnalysisClaimDisposition.TERMINAL, null);
    }

    public AnalysisJob requireActiveWorkerJob(Long jobId, String workerId, String claimToken) {
        requireWorkerId(workerId);
        String leaseTokenHash = hashClaimToken(claimToken);
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null) {
            throw new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND",
                    "Recording analysis job was not found.");
        }
        if (!RUNNING.equals(job.getStatus())
                || !workerId.equals(job.getClaimedBy())
                || !constantTimeEquals(leaseTokenHash, job.getLeaseTokenHash())
                || job.getClaimExpiresAt() == null
                || !job.getClaimExpiresAt().isAfter(Instant.now())) {
            throw leaseConflict();
        }
        return job;
    }

    @Transactional
    public Instant renewLease(Long jobId, String workerId, String claimToken) {
        requireWorkerId(workerId);
        String leaseTokenHash = hashClaimToken(claimToken);
        Instant leaseExpiresAt = Instant.now().plusSeconds(claimLeaseSeconds);
        if (analysisJobMapper.renewWorkerLease(
                jobId, workerId, leaseTokenHash, leaseExpiresAt) != 1) {
            throw leaseConflict();
        }
        return leaseExpiresAt;
    }

    String hashClaimToken(String claimToken) {
        if (claimToken == null || claimToken.isBlank()) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED",
                    "Worker claim token is required.");
        }
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(claimToken.getBytes(StandardCharsets.UTF_8));
            return java.util.HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable.", exception);
        }
    }

    private void requireWorkerId(String workerId) {
        if (workerId == null || workerId.isBlank()) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED",
                    "Authenticated worker is required.");
        }
    }

    private boolean constantTimeEquals(String expectedHash, String actualHash) {
        if (actualHash == null) {
            return false;
        }
        return MessageDigest.isEqual(
                expectedHash.getBytes(StandardCharsets.UTF_8),
                actualHash.getBytes(StandardCharsets.UTF_8));
    }

    private ApiException leaseConflict() {
        return new ApiException(HttpStatus.CONFLICT, "WORKER_LEASE_CONFLICT",
                "Worker lease is missing, expired, or owned by another worker.");
    }

    private void populateLegacyLeaseExpiry(AnalysisJob job) {
        if (job.getClaimExpiresAt() == null && job.getStartedAt() != null) {
            job.setClaimExpiresAt(job.getStartedAt().plusSeconds(claimLeaseSeconds));
        }
    }

    private AnalysisJob requireJob(Long jobId) {
        AnalysisJob job = analysisJobMapper.findRecordingAnalysisById(jobId);
        if (job == null || !RUNNING.equals(job.getStatus())) {
            throw new IllegalStateException("Claimed recording analysis job could not be reloaded: " + jobId);
        }
        return job;
    }
}
