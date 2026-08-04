package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistrationResult;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.util.Objects;
import org.springframework.dao.DuplicateKeyException;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingCommandService {

    private final CameraMapper cameraMapper;
    private final RecordingMapper recordingMapper;
    private final RecordingRequestValidator requestValidator;
    private final StorageObjectVerifier storageObjectVerifier;
    private final RecordingRegistrationWriter registrationWriter;
    private final long maxFileSizeBytes;

    public RecordingCommandService(
            CameraMapper cameraMapper,
            RecordingMapper recordingMapper,
            RecordingRequestValidator requestValidator,
            StorageObjectVerifier storageObjectVerifier,
            RecordingRegistrationWriter registrationWriter,
            MinioProperties minioProperties) {
        this.cameraMapper = cameraMapper;
        this.recordingMapper = recordingMapper;
        this.requestValidator = requestValidator;
        this.storageObjectVerifier = storageObjectVerifier;
        this.registrationWriter = registrationWriter;
        this.maxFileSizeBytes = minioProperties.getMaxFileSizeBytes();
    }

    public RecordingCreateResult create(
            MediaServerPrincipal principal,
            String cameraCode,
            String idempotencyKey,
            RecordingCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }

        NormalizedRecordingCreateRequest normalized = requestValidator.validate(
                cameraCode, idempotencyKey, request);
        Camera camera = requireOwnedCamera(cameraCode, principal.mediaServerId());

        RecordingRegistrationResult existingRegistration = recordingMapper.findRegistrationByKey(
                principal.mediaServerId(), normalized.idempotencyKey());
        if (existingRegistration != null) {
            return resolveRegistration(existingRegistration, normalized.requestFingerprint());
        }

        if (recordingMapper.findByS3Key(normalized.objectKey()) != null) {
            throw duplicateResource();
        }

        long fileSize = verifyStorageObject(normalized.objectKey());
        try {
            Recording created = registrationWriter.create(principal.mediaServerId(), normalized, fileSize);
            return new RecordingCreateResult(created, false);
        } catch (DuplicateKeyException exception) {
            return resolveConcurrentDuplicate(principal.mediaServerId(), normalized, exception);
        }
    }

    private Camera requireOwnedCamera(String cameraCode, long mediaServerId) {
        Camera camera = cameraMapper.findByCameraCode(cameraCode)
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), mediaServerId)) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED",
                    "Camera does not belong to the authenticated media server");
        }
        return camera;
    }

    private long verifyStorageObject(String objectKey) {
        StorageObject storageObject;
        try {
            storageObject = storageObjectVerifier.stat(objectKey);
        } catch (StorageObjectNotFoundException exception) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_NOT_FOUND",
                    "Storage object was not found");
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "Storage object could not be verified");
        }

        if (storageObject.size() <= 0) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_INVALID",
                    "Storage object is empty or invalid");
        }
        if (storageObject.size() > maxFileSizeBytes) {
            throw new ApiException(HttpStatus.CONTENT_TOO_LARGE, "FILE_TOO_LARGE",
                    "Storage object exceeds the configured size limit");
        }
        return storageObject.size();
    }

    private RecordingCreateResult resolveConcurrentDuplicate(
            long mediaServerId,
            NormalizedRecordingCreateRequest request,
            DuplicateKeyException originalException) {
        RecordingRegistrationResult registration = recordingMapper.findRegistrationByKey(
                mediaServerId, request.idempotencyKey());
        if (registration != null) {
            return resolveRegistration(registration, request.requestFingerprint());
        }
        if (recordingMapper.findByS3Key(request.objectKey()) != null) {
            throw duplicateResource();
        }
        throw originalException;
    }

    private RecordingCreateResult resolveRegistration(
            RecordingRegistrationResult registration, String requestFingerprint) {
        if (!Objects.equals(registration.getRequestFingerprint(), requestFingerprint)) {
            throw new ApiException(HttpStatus.CONFLICT, "IDEMPOTENCY_KEY_CONFLICT",
                    "Idempotency-Key was already used for a different request");
        }
        if (registration.getRecording() == null) {
            throw new IllegalStateException("Idempotency record does not reference a recording");
        }
        return new RecordingCreateResult(registration.getRecording(), true);
    }

    private ApiException duplicateResource() {
        return new ApiException(HttpStatus.CONFLICT, "DUPLICATE_RESOURCE",
                "Storage object is already registered");
    }
}
