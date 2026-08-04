package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.AiWorkerProperties;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerCompleteRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerEvidenceUploadUrlRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerEvidenceUploadUrlResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerFailRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobStatusResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerProtocol;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.mapper.AnalysisJobMapper;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.recording.messaging.RecordingAnalysisJobPublisher;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.util.ArrayList;
import java.util.HexFormat;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import java.util.UUID;
import java.util.regex.Pattern;
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
    private static final int MAX_MODEL_KEY_LENGTH = 100;
    private static final int MAX_ATTRIBUTE_SUMMARY_LENGTH = 2_000;
    private static final int MAX_OBJECT_KEY_LENGTH = 500;
    private static final Pattern CANDIDATE_KEY_PATTERN =
            Pattern.compile("^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$");
    private static final Set<String> RESULT_FIELDS = Set.of(
            "schemaVersion", "modelKey", "candidates", "inferenceDurationMs");
    private static final Set<String> CANDIDATE_FIELDS = Set.of(
            "candidateKey", "frameOffsetMs", "similarity", "boundingBox",
            "attributeSummary", "cropObjectKey", "frameObjectKey");
    private static final Set<String> BOUNDING_BOX_FIELDS = Set.of("x", "y", "width", "height");

    private final AnalysisJobMapper analysisJobMapper;
    private final RecordingMapper recordingMapper;
    private final CameraMapper cameraMapper;
    private final StorageObjectUrlSigner storageObjectUrlSigner;
    private final CandidateEventObjectKeyFactory objectKeyFactory;
    private final S3Properties s3Properties;
    private final RecordingAnalysisBatchResultService batchResultService;
    private final RecordingAnalysisJobPublisher recordingAnalysisJobPublisher;
    private final AiWorkerProperties properties;
    private final ObjectMapper objectMapper;

    public AiWorkerJobService(
            AnalysisJobMapper analysisJobMapper,
            RecordingMapper recordingMapper,
            CameraMapper cameraMapper,
            StorageObjectUrlSigner storageObjectUrlSigner,
            CandidateEventObjectKeyFactory objectKeyFactory,
            S3Properties s3Properties,
            RecordingAnalysisBatchResultService batchResultService,
            RecordingAnalysisJobPublisher recordingAnalysisJobPublisher,
            AiWorkerProperties properties,
            ObjectMapper objectMapper) {
        this.analysisJobMapper = analysisJobMapper;
        this.recordingMapper = recordingMapper;
        this.cameraMapper = cameraMapper;
        this.storageObjectUrlSigner = storageObjectUrlSigner;
        this.objectKeyFactory = objectKeyFactory;
        this.s3Properties = s3Properties;
        this.batchResultService = batchResultService;
        this.recordingAnalysisJobPublisher = recordingAnalysisJobPublisher;
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

    /**
     * Claims exactly the job announced by RabbitMQ. A stale or already-owned
     * broker delivery is acknowledged by the notebook worker through the empty
     * response, rather than causing it to claim an unrelated queued job.
     */
    @Transactional
    public AiWorkerClaimResponse claimJob(Long jobId, AiWorkerClaimRequest request) {
        AnalysisJob job = analysisJobMapper.findByIdForWorker(jobId);
        if (job == null) {
            return AiWorkerClaimResponse.empty(
                    AiWorkerProtocol.VERSION, properties.getEmptyPollAfterMs());
        }

        Recording recording = requireRecording(job.getRecordingId());
        Camera camera = cameraMapper.findById(recording.getCameraId())
                .orElseThrow(() -> notFound("Recording camera was not found."));
        Instant leaseExpiresAt = Instant.now().plus(properties.getLeaseDuration());
        String leaseToken = UUID.randomUUID().toString();
        int updated = analysisJobMapper.claim(
                job.getId(), request.workerId(), hash(leaseToken), leaseExpiresAt);
        if (updated != 1) {
            return AiWorkerClaimResponse.empty(
                    AiWorkerProtocol.VERSION, properties.getEmptyPollAfterMs());
        }
        AiWorkerJobResponse response = toJobResponse(job, recording, camera,
                request.modelKey(), leaseExpiresAt);
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

    public AiWorkerEvidenceUploadUrlResponse createEvidenceUploadUrls(
            Long jobId, AiWorkerEvidenceUploadUrlRequest request) {
        AnalysisJob job = analysisJobMapper.findByIdForWorker(jobId);
        requireActiveLease(job, request.workerId(), request.leaseToken());
        Set<String> candidateKeys = new HashSet<>();
        if (request.candidates().stream()
                .anyMatch(candidate -> !candidateKeys.add(candidate.candidateKey()))) {
            throw invalidResult("AI Worker evidence candidateKey must be unique.");
        }
        int attempt = job.getRetryCount() + 1;
        var uploads = request.candidates().stream()
                .map(candidate -> signedUpload(jobId, attempt, candidate))
                .toList();
        return new AiWorkerEvidenceUploadUrlResponse(
                AiWorkerProtocol.VERSION,
                jobId,
                attempt,
                s3Properties.getPresignedUrlExpiry().toSeconds(),
                uploads);
    }

    public AiWorkerJobStatusResponse complete(Long jobId, AiWorkerCompleteRequest request) {
        AnalysisJob job = analysisJobMapper.findByIdForWorker(jobId);
        if (job == null) {
            throw notFound("AI Worker job was not found.");
        }
        JsonNode result = validateResult(job, request.result());
        String resultPayload = serialize(result);
        if (resultPayload.getBytes(StandardCharsets.UTF_8).length > properties.getMaxResultBytes()) {
            throw invalidResult("AI Worker result exceeds the configured size limit.");
        }
        String resultModelKey = result.path("modelKey").asText("");
        String resultDigest = hash(resultPayload);
        RecordingAnalysisBatchResultRequest batchRequest = toBatchResultRequest(job, result, resultDigest);
        batchResultService.completeFromAiWorker(
                jobId,
                batchRequest,
                request.workerId(),
                hash(request.leaseToken()),
                resultModelKey,
                resultPayload,
                resultDigest);
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
        if (requeue) {
            recordingAnalysisJobPublisher.enqueue(jobId, job.getCaseId());
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
                searchFromMs,
                searchToMs,
                leaseExpiresAt);
    }

    private AiWorkerEvidenceUploadUrlResponse.Upload signedUpload(
            Long jobId,
            int attempt,
            AiWorkerEvidenceUploadUrlRequest.Candidate candidate) {
        String frameObjectKey = objectKeyFactory.analysisFrameKey(
                jobId, attempt, candidate.candidateKey(), candidate.frameContentType());
        String cropObjectKey = objectKeyFactory.analysisCropKey(
                jobId, attempt, candidate.candidateKey(), candidate.cropContentType());
        try {
            return new AiWorkerEvidenceUploadUrlResponse.Upload(
                    candidate.candidateKey(),
                    frameObjectKey,
                    storageObjectUrlSigner.createPutUrl(frameObjectKey),
                    cropObjectKey,
                    storageObjectUrlSigner.createPutUrl(cropObjectKey));
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "AI Worker evidence upload URL could not be created");
        }
    }

    private RecordingAnalysisBatchResultRequest toBatchResultRequest(
            AnalysisJob job, JsonNode result, String resultDigest) {
        Recording recording = requireRecording(job.getRecordingId());
        long searchFromMs = effectiveSearchFromMs(job, recording);
        long searchToMs = effectiveSearchToMs(job, recording);
        var candidates = new ArrayList<RecordingAnalysisBatchResultRequest.Candidate>();
        for (JsonNode candidate : result.path("candidates")) {
            long frameOffsetMs = candidate.path("frameOffsetMs").longValue();
            if (frameOffsetMs < searchFromMs || frameOffsetMs >= searchToMs) {
                throw invalidResult("AI Worker candidate is outside the requested search window.");
            }
            JsonNode box = candidate.path("boundingBox");
            candidates.add(new RecordingAnalysisBatchResultRequest.Candidate(
                    candidate.path("candidateKey").asText(),
                    OffsetDateTime.ofInstant(
                            recording.getStartTime().plusMillis(frameOffsetMs), ZoneOffset.UTC),
                    candidate.path("similarity").decimalValue(),
                    candidate.path("frameObjectKey").asText(),
                    candidate.path("cropObjectKey").asText(),
                    new RecordingAnalysisBatchResultRequest.BoundingBox(
                            box.path("x").intValue(),
                            box.path("y").intValue(),
                            box.path("width").intValue(),
                            box.path("height").intValue())));
        }
        int attempt = job.getRetryCount() + 1;
        return new RecordingAnalysisBatchResultRequest(
                "ai-worker-%d-attempt-%d-%s".formatted(job.getId(), attempt, resultDigest),
                List.copyOf(candidates));
    }

    private long effectiveSearchFromMs(AnalysisJob job, Recording recording) {
        Instant effectiveStart = recording.getStartTime();
        if (job.getSearchStartSnapshot() != null
                && job.getSearchStartSnapshot().isAfter(effectiveStart)) {
            effectiveStart = job.getSearchStartSnapshot();
        }
        return Duration.between(recording.getStartTime(), effectiveStart).toMillis();
    }

    private long effectiveSearchToMs(AnalysisJob job, Recording recording) {
        Instant effectiveEnd = recording.getEndTime();
        if (job.getSearchEndSnapshot() != null
                && job.getSearchEndSnapshot().isBefore(effectiveEnd)) {
            effectiveEnd = job.getSearchEndSnapshot();
        }
        long searchToMs = Duration.between(recording.getStartTime(), effectiveEnd).toMillis();
        if (effectiveSearchFromMs(job, recording) >= searchToMs) {
            throw invalidResult("Recording does not overlap the requested search window.");
        }
        return searchToMs;
    }

    private JsonNode validateResult(AnalysisJob job, JsonNode result) {
        if (result == null || !result.isObject()
                || !AiWorkerProtocol.VERSION.equals(result.path("schemaVersion").asText())
                || result.path("candidates").isMissingNode()
                || !result.path("candidates").isArray()
                || result.path("candidates").size() > AiWorkerProtocol.MAX_CANDIDATES
                || !hasOnlyFields(result, RESULT_FIELDS)
                || !result.path("inferenceDurationMs").isIntegralNumber()
                || !result.path("inferenceDurationMs").canConvertToLong()
                || result.path("inferenceDurationMs").longValue() < 0) {
            throw invalidResult("AI Worker result schema is invalid.");
        }
        if (!validRequiredText(result.path("modelKey"), MAX_MODEL_KEY_LENGTH)) {
            throw invalidResult("AI Worker result modelKey is required.");
        }
        Set<String> candidateKeys = new HashSet<>();
        int attempt = job.getRetryCount() + 1;
        for (JsonNode candidate : result.path("candidates")) {
            String candidateKey = candidate.path("candidateKey").asText("");
            if (!candidate.isObject()
                    || !hasOnlyFields(candidate, CANDIDATE_FIELDS)
                    || !validCandidateKey(candidateKey)
                    || !candidateKeys.add(candidateKey)
                    || !candidate.path("frameOffsetMs").isIntegralNumber()
                    || !candidate.path("frameOffsetMs").canConvertToLong()
                    || candidate.path("frameOffsetMs").longValue() < 0
                    || !candidate.path("similarity").isNumber()
                    || candidate.path("similarity").decimalValue().compareTo(BigDecimal.ZERO) < 0
                    || candidate.path("similarity").decimalValue().compareTo(BigDecimal.ONE) > 0
                    || !validOptionalText(candidate.path("attributeSummary"), MAX_ATTRIBUTE_SUMMARY_LENGTH)
                    || !validRequiredText(candidate.path("frameObjectKey"), MAX_OBJECT_KEY_LENGTH)
                    || !validRequiredText(candidate.path("cropObjectKey"), MAX_OBJECT_KEY_LENGTH)
                    || !objectKeyFactory.matchesAnalysisFrameKey(
                            job.getId(), attempt, candidateKey,
                            candidate.path("frameObjectKey").asText())
                    || !objectKeyFactory.matchesAnalysisCropKey(
                            job.getId(), attempt, candidateKey,
                            candidate.path("cropObjectKey").asText())
                    || !validBoundingBox(candidate.path("boundingBox"))) {
                throw invalidResult("AI Worker result contains an invalid candidate.");
            }
        }
        return result;
    }

    private boolean validBoundingBox(JsonNode box) {
        return box.isObject()
                && hasOnlyFields(box, BOUNDING_BOX_FIELDS)
                && validNonNegativeInt(box.path("x"))
                && validNonNegativeInt(box.path("y"))
                && validPositiveInt(box.path("width"))
                && validPositiveInt(box.path("height"));
    }

    private boolean validCandidateKey(String candidateKey) {
        return CANDIDATE_KEY_PATTERN.matcher(candidateKey).matches();
    }

    private boolean validRequiredText(JsonNode node, int maximumLength) {
        return node.isTextual() && !node.asText().isBlank() && node.asText().length() <= maximumLength;
    }

    private boolean validOptionalText(JsonNode node, int maximumLength) {
        return node.isMissingNode() || node.isNull()
                || node.isTextual() && node.asText().length() <= maximumLength;
    }

    private boolean validNonNegativeInt(JsonNode node) {
        return node.isIntegralNumber() && node.canConvertToInt() && node.intValue() >= 0;
    }

    private boolean validPositiveInt(JsonNode node) {
        return node.isIntegralNumber() && node.canConvertToInt() && node.intValue() > 0;
    }

    private boolean hasOnlyFields(JsonNode node, Set<String> allowedFields) {
        return allowedFields.containsAll(node.propertyNames());
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

    private void requireActiveLease(AnalysisJob job, String workerId, String leaseToken) {
        if (job == null || !RUNNING.equals(job.getStatus())
                || !Objects.equals(workerId, job.getClaimedBy())
                || !Objects.equals(hash(leaseToken), job.getLeaseTokenHash())
                || job.getClaimExpiresAt() == null
                || !job.getClaimExpiresAt().isAfter(Instant.now())) {
            throw leaseConflict();
        }
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
