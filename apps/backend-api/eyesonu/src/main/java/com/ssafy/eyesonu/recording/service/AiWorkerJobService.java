package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerCompleteRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerFailRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobStatusResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerProtocol;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.util.HexFormat;
import java.util.UUID;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.ObjectMapper;

@Service
public class AiWorkerJobService {

    private static final String RUNNING = "RUNNING";
    private static final String QUEUED = "QUEUED";
    private static final String SUCCEEDED = "SUCCEEDED";
    private static final String FAILED = "FAILED";

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final StorageObjectUrlSigner storageObjectUrlSigner;
    private final AiWorkerProperties properties;
    private final ObjectMapper objectMapper;

    public AiWorkerJobService(
            AnalysisJobMapper analysisJobMapper,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            StorageObjectUrlSigner storageObjectUrlSigner,
            AiWorkerProperties properties,
            ObjectMapper objectMapper) {
        this.analysisJobMapper = analysisJobMapper;
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.storageObjectUrlSigner = storageObjectUrlSigner;
        this.properties = properties;
        this.objectMapper = objectMapper;
    }

    @Transactional
    public AiWorkerClaimResponse claim(AiWorkerClaimRequest request) {
        AnalysisJob job = analysisJobMapper.findNextClaimableForUpdate();
        if (job == null) {
            return AiWorkerClaimResponse.empty(
                    AiWorkerProtocol.VERSION, properties.getEmptyPollAfterMs());
        }

        Recording recording = requireRecording(job.getRecordingId());
        Camera camera = cameraMapper.findById(recording.getCameraId())
                .orElseThrow(() -> notFound("Recording camera was not found."));
        Instant leaseExpiresAt = Instant.now().plus(properties.getLeaseDuration());
        String leaseToken = UUID.randomUUID().toString();
        AiWorkerJobResponse response = toJobResponse(job, recording, camera,
                request.modelKey(), leaseExpiresAt);
        int updated = analysisJobMapper.claim(
                job.getId(), request.workerId(), hash(leaseToken), leaseExpiresAt);
        if (updated != 1) {
            throw leaseConflict();
        }
        return new AiWorkerClaimResponse(
                AiWorkerProtocol.VERSION, response, leaseToken, leaseExpiresAt, 0);
    }

    @Transactional
    public AiWorkerHeartbeatResponse heartbeat(Long jobId, AiWorkerHeartbeatRequest request) {
        Instant leaseExpiresAt = Instant.now().plus(properties.getLeaseDuration());
        int updated = analysisJobMapper.heartbeat(
                jobId, request.workerId(), hash(request.leaseToken()), leaseExpiresAt);
        if (updated != 1) {
            throw leaseConflict();
        }
        return new AiWorkerHeartbeatResponse(
                AiWorkerProtocol.VERSION, jobId, RUNNING, leaseExpiresAt);
    }

    @Transactional
    public AiWorkerJobStatusResponse complete(Long jobId, AiWorkerCompleteRequest request) {
        JsonNode result = validateResult(request.result());
        String resultPayload = serialize(result);
        if (resultPayload.getBytes(StandardCharsets.UTF_8).length > properties.getMaxResultBytes()) {
            throw invalidResult("AI Worker result exceeds the configured size limit.");
        }
        String resultModelKey = result.path("modelKey").asText("");
        String resultDigest = hash(resultPayload);
        int updated = analysisJobMapper.complete(
                jobId,
                request.workerId(),
                hash(request.leaseToken()),
                resultModelKey,
                resultPayload,
                resultDigest);
        if (updated != 1) {
            throw leaseConflict();
        }
        return new AiWorkerJobStatusResponse(
                AiWorkerProtocol.VERSION, jobId, SUCCEEDED,
                request.workerId(), resultModelKey, resultDigest);
    }

    @Transactional
    public AiWorkerJobStatusResponse fail(Long jobId, AiWorkerFailRequest request) {
        AnalysisJob job = analysisJobMapper.findByIdForWorker(jobId);
        if (job == null) {
            throw notFound("AI Worker job was not found.");
        }
        boolean requeue = request.retryable() && job.getRetryCount() < properties.getMaxRetryCount();
        String nextStatus = requeue ? QUEUED : FAILED;
        String errorMessage = request.errorCode() + ": " + request.errorMessage();
        int updated = analysisJobMapper.fail(
                jobId,
                request.workerId(),
                hash(request.leaseToken()),
                nextStatus,
                errorMessage.substring(
                        0,
                        Math.min(errorMessage.length(), AiWorkerProtocol.MAX_ERROR_MESSAGE_LENGTH)));
        if (updated != 1) {
            throw leaseConflict();
        }
        return new AiWorkerJobStatusResponse(
                AiWorkerProtocol.VERSION, jobId, nextStatus, request.workerId(), null, null);
    }

    private AiWorkerJobResponse toJobResponse(
            AnalysisJob job,
            Recording recording,
            Camera camera,
            String modelKey,
            Instant leaseExpiresAt) {
        Instant effectiveStart = recording.getStartTime();
        if (job.getSearchStartSnapshot() != null
                && job.getSearchStartSnapshot().isAfter(effectiveStart)) {
            effectiveStart = job.getSearchStartSnapshot();
        }
        Instant effectiveEnd = recording.getEndTime();
        if (job.getSearchEndSnapshot() != null
                && job.getSearchEndSnapshot().isBefore(effectiveEnd)) {
            effectiveEnd = job.getSearchEndSnapshot();
        }
        if (!effectiveStart.isBefore(effectiveEnd)) {
            throw invalidResult("Recording does not overlap the requested search window.");
        }
        long searchFromMs = Duration.between(recording.getStartTime(), effectiveStart).toMillis();
        Long searchToMs = Duration.between(recording.getStartTime(), effectiveEnd).toMillis();
        String cameraName = camera.cameraName() == null
                ? camera.cameraCode() : camera.cameraName();
        String cameraAddress = camera.cameraCode() == null
                ? "camera-" + camera.id() : camera.cameraCode();
        return new AiWorkerJobResponse(
                AiWorkerProtocol.VERSION,
                job.getId(),
                job.getCaseId(),
                job.getSearchConditionId(),
                job.getRecordingId(),
                modelKey,
                camera.id(),
                cameraName,
                cameraAddress,
                storageObjectUrlSigner.createGetUrl(recording.getS3Key()),
                null,
                recording.getStartTime(),
                recording.getEndTime(),
                job.getPromptSnapshot() == null ? "" : job.getPromptSnapshot(),
                job.getExclusionPromptSnapshot(),
                job.getSimilarityThresholdSnapshot() == null
                        ? java.math.BigDecimal.ZERO : job.getSimilarityThresholdSnapshot(),
                searchFromMs,
                searchToMs,
                leaseExpiresAt);
    }

    private JsonNode validateResult(JsonNode result) {
        if (result == null || !result.isObject()
                || !AiWorkerProtocol.VERSION.equals(result.path("schemaVersion").asText())
                || result.path("candidates").isMissingNode()
                || !result.path("candidates").isArray()
                || result.path("candidates").size() > AiWorkerProtocol.MAX_CANDIDATES
                || result.path("inferenceDurationMs").isMissingNode()) {
            throw invalidResult("AI Worker result schema is invalid.");
        }
        if (result.path("modelKey").asText("").isBlank()) {
            throw invalidResult("AI Worker result modelKey is required.");
        }
        for (JsonNode candidate : result.path("candidates")) {
            if (!candidate.isObject() || candidate.has("cropPath") || candidate.has("videoPath")) {
                throw invalidResult("AI Worker result must not contain local notebook paths.");
            }
        }
        return result;
    }

    private String serialize(JsonNode result) {
        try {
            return objectMapper.writeValueAsString(result);
        } catch (JacksonException exception) {
            throw invalidResult("AI Worker result could not be serialized.");
        }
    }

    private Recording requireRecording(Long recordingId) {
        Recording recording = recordingMapper.findById(recordingId);
        if (recording == null) {
            throw notFound("Recording was not found.");
        }
        return recording;
    }

    private String hash(String value) {
        try {
            byte[] digest = MessageDigest.getInstance("SHA-256")
                    .digest(value.getBytes(StandardCharsets.UTF_8));
            return HexFormat.of().formatHex(digest);
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is unavailable.", exception);
        }
    }

    private ApiException leaseConflict() {
        return new ApiException(HttpStatus.CONFLICT, "AI_WORKER_LEASE_CONFLICT",
                "The AI Worker lease is missing, expired, or owned by another worker.");
    }

    private ApiException notFound(String message) {
        return new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", message);
    }

    private ApiException invalidResult(String message) {
        return new ApiException(HttpStatus.UNPROCESSABLE_ENTITY, "AI_WORKER_RESULT_INVALID", message);
    }
}
