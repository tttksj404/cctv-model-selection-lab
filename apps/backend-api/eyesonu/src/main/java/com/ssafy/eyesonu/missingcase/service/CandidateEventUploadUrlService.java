package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateResponse;
import com.ssafy.eyesonu.missingcase.mapper.CandidateEventMapper;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.util.HashSet;
import java.util.List;
import java.util.Objects;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class CandidateEventUploadUrlService {

    private final CameraMapper cameraMapper;
    private final CandidateEventMapper candidateEventMapper;
    private final CaseQueryService caseQueryService;
    private final CandidateEventObjectKeyFactory objectKeyFactory;
    private final StorageObjectUrlSigner urlSigner;
    private final MinioProperties minioProperties;

    public CandidateEventUploadUrlService(
            CameraMapper cameraMapper,
            CandidateEventMapper candidateEventMapper,
            CaseQueryService caseQueryService,
            CandidateEventObjectKeyFactory objectKeyFactory,
            StorageObjectUrlSigner urlSigner,
            MinioProperties minioProperties) {
        this.cameraMapper = cameraMapper;
        this.candidateEventMapper = candidateEventMapper;
        this.caseQueryService = caseQueryService;
        this.objectKeyFactory = objectKeyFactory;
        this.urlSigner = urlSigner;
        this.minioProperties = minioProperties;
    }

    public CandidateEventUploadUrlCreateResponse create(
            MediaServerPrincipal principal,
            CandidateEventUploadUrlCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        Camera camera = cameraMapper.findByCameraCode(request.cameraCode()).orElseThrow(() ->
                new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), principal.mediaServerId())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED",
                    "Camera does not belong to the authenticated media server");
        }
        if (caseQueryService.require(request.caseId()).getStatus() != CaseStatus.SEARCHING) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "CASE_NOT_SEARCHABLE", "Case is not searchable");
        }
        if (!candidateEventMapper.existsActiveCaseCamera(request.caseId(), camera.id())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "CAMERA_NOT_SELECTED",
                    "Camera is not selected for this case");
        }
        validateUniqueTrackIds(request.detections());

        String frameKey = objectKeyFactory.frameKey(principal.mediaServerId(), camera.id(), request.caseId(),
                request.eventId(), request.frame().contentType());
        CandidateEventUploadUrlCreateResponse.Upload frame = new CandidateEventUploadUrlCreateResponse.Upload(
                frameKey, sign(frameKey), request.frame().contentType());
        List<CandidateEventUploadUrlCreateResponse.DetectionUpload> detections = request.detections().stream()
                .map(detection -> detectionUpload(principal, camera, request, detection))
                .toList();
        return new CandidateEventUploadUrlCreateResponse(
                frame, detections, minioProperties.getPresignedUrlExpiry().toSeconds());
    }

    private CandidateEventUploadUrlCreateResponse.DetectionUpload detectionUpload(
            MediaServerPrincipal principal,
            Camera camera,
            CandidateEventUploadUrlCreateRequest request,
            CandidateEventUploadUrlCreateRequest.Detection detection) {
        String objectKey = objectKeyFactory.cropKey(principal.mediaServerId(), camera.id(), request.caseId(),
                request.eventId(), detection.trackId(), detection.contentType());
        return new CandidateEventUploadUrlCreateResponse.DetectionUpload(
                detection.trackId(), objectKey, sign(objectKey), detection.contentType());
    }

    private String sign(String objectKey) {
        try {
            return urlSigner.createPutUrl(objectKey);
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE",
                    "Image upload URL could not be created");
        }
    }

    private void validateUniqueTrackIds(List<CandidateEventUploadUrlCreateRequest.Detection> detections) {
        Set<String> trackIds = new HashSet<>();
        if (detections.stream().anyMatch(detection -> !trackIds.add(detection.trackId()))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "trackId must be unique");
        }
    }
}
