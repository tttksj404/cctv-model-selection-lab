package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Component;

@Component
public class CandidateEventAccessValidator {

    private final CameraMapper cameraMapper;
    private final CandidateEventObjectKeyFactory objectKeyFactory;

    public CandidateEventAccessValidator(
            CameraMapper cameraMapper,
            CandidateEventObjectKeyFactory objectKeyFactory) {
        this.cameraMapper = cameraMapper;
        this.objectKeyFactory = objectKeyFactory;
    }

    public Camera validateCameraAccess(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED,
                    "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        validateKeys(request);
        Camera camera = cameraMapper.findByCameraCode(request.cameraCode()).orElseThrow(() ->
                new ApiException(HttpStatus.NOT_FOUND,
                        "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), principal.mediaServerId())) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "ACCESS_DENIED", "Camera does not belong to the authenticated media server");
        }
        return camera;
    }

    public Camera validateRealtimeAccess(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request) {
        Camera camera = validateCameraAccess(principal, request);
        boolean validFrame = objectKeyFactory.matchesFrameKey(
                principal.mediaServerId(), camera.id(), request.caseId(),
                request.eventId(), request.frameObjectKey());
        boolean validCrops = request.detections().stream().allMatch(detection ->
                objectKeyFactory.matchesCropKey(
                        principal.mediaServerId(), camera.id(), request.caseId(),
                        request.eventId(), detection.trackId(), detection.cropObjectKey()));
        if (!validFrame || !validCrops) {
            throw new ApiException(HttpStatus.BAD_REQUEST,
                    "INVALID_UPLOAD_OBJECT_KEY",
                    "Image object key was not issued for this candidate event");
        }
        return camera;
    }

    private void validateKeys(CandidateEventCreateRequest request) {
        if (invalidKey(request.frameObjectKey())
                || request.detections().stream()
                .anyMatch(detection -> invalidKey(detection.cropObjectKey()))) {
            throw new ApiException(HttpStatus.BAD_REQUEST,
                    "VALIDATION_ERROR", "Invalid object key");
        }
    }

    private boolean invalidKey(String key) {
        return key == null || key.isBlank() || key.contains("\\") || key.contains("..")
                || key.chars().anyMatch(Character::isISOControl);
    }
}
