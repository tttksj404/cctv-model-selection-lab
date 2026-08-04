package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateResponse;
import com.ssafy.eyesonu.recording.mapper.RecordingMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingUploadUrlService {

    private static final String RECORDING_CONTENT_TYPE = "video/mp4";

    private final CameraMapper cameraMapper;
    private final RecordingMapper recordingMapper;
    private final RecordingRequestValidator requestValidator;
    private final StorageObjectUrlSigner urlSigner;
    private final MinioProperties minioProperties;

    public RecordingUploadUrlService(
            CameraMapper cameraMapper,
            RecordingMapper recordingMapper,
            RecordingRequestValidator requestValidator,
            StorageObjectUrlSigner urlSigner,
            MinioProperties minioProperties) {
        this.cameraMapper = cameraMapper;
        this.recordingMapper = recordingMapper;
        this.requestValidator = requestValidator;
        this.urlSigner = urlSigner;
        this.minioProperties = minioProperties;
    }

    public RecordingUploadUrlCreateResponse create(
            MediaServerPrincipal principal,
            String cameraCode,
            String idempotencyKey,
            RecordingUploadUrlCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }

        NormalizedRecordingUploadRequest normalized = requestValidator.validateUpload(
                cameraCode, idempotencyKey, request);
        Camera camera = cameraMapper.findByCameraCode(cameraCode)
                .orElseThrow(() -> new ApiException(
                        HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), principal.mediaServerId())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED",
                    "Camera does not belong to the authenticated media server");
        }
        if (recordingMapper.findRegistrationByKey(
                principal.mediaServerId(), normalized.idempotencyKey()) != null) {
            throw new ApiException(HttpStatus.CONFLICT, "RECORDING_ALREADY_REGISTERED",
                    "Recording was already registered for this Idempotency-Key");
        }

        String uploadUrl;
        try {
            uploadUrl = urlSigner.createPutUrl(normalized.objectKey());
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "Recording upload URL could not be created");
        }

        return new RecordingUploadUrlCreateResponse(
                normalized.objectKey(),
                uploadUrl,
                RECORDING_CONTENT_TYPE,
                minioProperties.getPresignedUrlExpiry().toSeconds(),
                minioProperties.getMaxFileSizeBytes());
    }
}
