package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.common.config.properties.S3Properties;
import com.ssafy.eyesonu.missingcase.domain.CandidateAggregate;
import com.ssafy.eyesonu.missingcase.domain.CandidateEvent;
import com.ssafy.eyesonu.missingcase.domain.CandidateEventDetection;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.mapper.CandidateEventMapper;
import com.ssafy.eyesonu.storage.StorageObjectNotFoundException;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.time.Instant;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.List;
import java.util.Objects;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class CandidateEventCommandService {
    private final CameraMapper cameraMapper;
    private final CandidateEventMapper mapper;
    private final CaseQueryService caseQueryService;
    private final StorageObjectVerifier storageObjectVerifier;
    private final CandidateEventObjectKeyFactory objectKeyFactory;
    private final S3Properties s3Properties;

    public CandidateEventCommandService(CameraMapper cameraMapper, CandidateEventMapper mapper,
                                        CaseQueryService caseQueryService,
                                        StorageObjectVerifier storageObjectVerifier,
                                        CandidateEventObjectKeyFactory objectKeyFactory,
                                        S3Properties s3Properties) {
        this.cameraMapper = cameraMapper;
        this.mapper = mapper;
        this.caseQueryService = caseQueryService;
        this.storageObjectVerifier = storageObjectVerifier;
        this.objectKeyFactory = objectKeyFactory;
        this.s3Properties = s3Properties;
    }

    @Transactional
    public CandidateEventCreateResponse create(MediaServerPrincipal principal,
                                               CandidateEventCreateRequest request) {
        return create(principal, request, null);
    }

    @Transactional
    public CandidateEventCreateResponse create(MediaServerPrincipal principal,
                                               CandidateEventCreateRequest request,
                                               Long expectedCameraId) {
        if (principal == null || principal.mediaServerId() == null) {
            throw new ApiException(HttpStatus.UNAUTHORIZED, "AUTHENTICATION_REQUIRED", "Authentication is required");
        }
        validateKeys(request);
        Camera camera = cameraMapper.findByCameraCode(request.cameraCode()).orElseThrow(() ->
                new ApiException(HttpStatus.NOT_FOUND, "RESOURCE_NOT_FOUND", "Camera was not found"));
        if (!Objects.equals(camera.mediaServerId(), principal.mediaServerId())) {
            throw new ApiException(HttpStatus.FORBIDDEN, "ACCESS_DENIED", "Camera does not belong to the authenticated media server");
        }
        if (expectedCameraId != null && !Objects.equals(camera.id(), expectedCameraId)) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "CAMERA_MISMATCH",
                    "Camera does not match the requested recording analysis job");
        }
        if (caseQueryService.require(request.caseId()).getStatus() != CaseStatus.SEARCHING) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "CASE_NOT_SEARCHABLE", "Case is not searchable");
        }
        if (!mapper.existsActiveCaseCamera(request.caseId(), camera.id())) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "CAMERA_NOT_SELECTED", "Camera is not selected for this case");
        }
        if (expectedCameraId == null) {
            validateRealtimeObjectKeys(principal, camera, request);
        }
        verifyObject(request.frameObjectKey());
        request.detections().forEach(detection -> verifyObject(detection.cropObjectKey()));

        CandidateEvent existing = mapper.findEventByEventId(request.eventId());
        if (existing != null) return duplicateResult(existing, request, camera.id());

        CandidateEvent event = new CandidateEvent();
        event.setEventId(request.eventId());
        event.setCaseId(request.caseId());
        event.setCameraId(camera.id());
        event.setDetectedAt(request.detectedAt().toInstant());
        event.setFrameObjectKey(request.frameObjectKey());
        int eventInserted = mapper.insertEvent(event);
        if (eventInserted == 0) {
            CandidateEvent concurrent = mapper.findEventByEventId(request.eventId());
            if (concurrent == null) {
                throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                        "EVENT_ID_UPSERT_FAILED", "Event could not be loaded after upsert");
            }
            return duplicateResult(concurrent, request, camera.id());
        }

        List<Integer> processingOrder = new ArrayList<>();
        for (int index = 0; index < request.detections().size(); index++) {
            processingOrder.add(index);
        }
        processingOrder.sort(Comparator.comparing(index -> request.detections().get(index).trackId()));

        List<Long> candidateIds = new ArrayList<>(Collections.nCopies(request.detections().size(), null));
        for (int index : processingOrder) {
            CandidateEventCreateRequest.Detection input = request.detections().get(index);
            String boundingBox = boundingBoxJson(input.boundingBox());
            CandidateAggregate candidate = newCandidate(request, camera.id(), input, boundingBox);
            int candidateInserted = mapper.insertCandidate(candidate);
            if (candidateInserted == 0) {
                candidate = mapper.findCandidateForUpdate(request.caseId(), camera.id(), input.trackId());
                if (candidate == null) {
                    throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                            "CANDIDATE_UPSERT_FAILED", "Candidate could not be loaded after upsert");
                }
                mapper.updateCandidate(candidate, request.detectedAt().toInstant(), input.similarity(),
                        input.cropObjectKey(), request.frameObjectKey(), boundingBox);
            }
            candidateIds.set(index, candidate.getId());
            CandidateEventDetection detection = new CandidateEventDetection();
            detection.setCandidateEventId(event.getId());
            detection.setCandidateId(candidate.getId());
            detection.setDetectionIndex(index);
            detection.setTrackId(input.trackId());
            detection.setCropObjectKey(input.cropObjectKey());
            detection.setSimilarity(input.similarity());
            detection.setBoundingBox(boundingBox);
            mapper.insertDetection(detection);
        }
        return new CandidateEventCreateResponse(event.getEventId(), event.getCaseId(), event.getCameraId(),
                request.detections().size(), candidateIds, false, event.getCreatedAt() == null ? Instant.now() : event.getCreatedAt());
    }

    private CandidateEventCreateResponse duplicateResult(CandidateEvent existing,
                                                         CandidateEventCreateRequest request,
                                                         Long cameraId) {
        List<CandidateEventDetection> stored = mapper.findDetectionsByEventId(request.eventId());
        boolean same = Objects.equals(existing.getCaseId(), request.caseId())
                && Objects.equals(existing.getCameraId(), cameraId)
                && Objects.equals(existing.getFrameObjectKey(), request.frameObjectKey())
                && Objects.equals(existing.getDetectedAt(), request.detectedAt().toInstant())
                && stored.size() == request.detections().size();
        if (same) {
            for (int i = 0; i < stored.size(); i++) {
                CandidateEventDetection saved = stored.get(i);
                CandidateEventCreateRequest.Detection input = request.detections().get(i);
                same &= Objects.equals(saved.getTrackId(), input.trackId())
                        && saved.getSimilarity().compareTo(input.similarity()) == 0
                        && Objects.equals(saved.getCropObjectKey(), input.cropObjectKey())
                        && Objects.equals(saved.getBoundingBox(), boundingBoxJson(input.boundingBox()));
            }
        }
        if (!same) throw new ApiException(HttpStatus.CONFLICT, "EVENT_ID_CONFLICT", "eventId was already used for a different event");
        List<Long> ids = stored.stream().map(CandidateEventDetection::getCandidateId).toList();
        return new CandidateEventCreateResponse(existing.getEventId(), existing.getCaseId(), existing.getCameraId(),
                stored.size(), ids, true, existing.getCreatedAt());
    }

    private CandidateAggregate newCandidate(CandidateEventCreateRequest request, Long cameraId,
                                             CandidateEventCreateRequest.Detection input, String box) {
        CandidateAggregate candidate = new CandidateAggregate();
        candidate.setCaseId(request.caseId()); candidate.setCameraId(cameraId); candidate.setTrackId(input.trackId());
        candidate.setFirstDetectedAt(request.detectedAt().toInstant()); candidate.setLastDetectedAt(request.detectedAt().toInstant());
        candidate.setBestSimilarity(input.similarity()); candidate.setAverageSimilarity(input.similarity());
        candidate.setDetectionCount(1); candidate.setSimilarity(input.similarity()); candidate.setCropObjectKey(input.cropObjectKey());
        candidate.setFrameObjectKey(request.frameObjectKey()); candidate.setBoundingBox(box);
        return candidate;
    }

    private void validateKeys(CandidateEventCreateRequest request) {
        if (invalidKey(request.frameObjectKey()) || request.detections().stream().anyMatch(d -> invalidKey(d.cropObjectKey()))) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", "Invalid object key");
        }
    }

    private boolean invalidKey(String key) {
        return key == null || key.isBlank() || key.contains("\\") || key.contains("..") || key.chars().anyMatch(Character::isISOControl);
    }

    private void verifyObject(String key) {
        try {
            StorageObject object = storageObjectVerifier.stat(key);
            if (object.size() <= 0) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_INVALID", "Storage object is empty");
            }
            if (object.size() > s3Properties.getCandidateImageMaxFileSizeBytes()) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_TOO_LARGE", "Storage object is too large");
            }
            if (!"image/jpeg".equals(object.contentType()) && !"image/png".equals(object.contentType())) {
                throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_TYPE_INVALID",
                        "Storage object must be a JPEG or PNG image");
            }
        } catch (StorageObjectNotFoundException e) {
            throw new ApiException(HttpStatus.UNPROCESSABLE_CONTENT, "STORAGE_OBJECT_NOT_FOUND", "Storage object was not found");
        } catch (StorageObjectUnavailableException e) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE, "STORAGE_UNAVAILABLE", "Storage object could not be verified");
        }
    }

    private void validateRealtimeObjectKeys(MediaServerPrincipal principal, Camera camera,
                                            CandidateEventCreateRequest request) {
        boolean validFrame = objectKeyFactory.matchesFrameKey(principal.mediaServerId(), camera.id(),
                request.caseId(), request.eventId(), request.frameObjectKey());
        boolean validCrops = request.detections().stream().allMatch(detection ->
                objectKeyFactory.matchesCropKey(principal.mediaServerId(), camera.id(), request.caseId(),
                        request.eventId(), detection.trackId(), detection.cropObjectKey()));
        if (!validFrame || !validCrops) {
            throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_UPLOAD_OBJECT_KEY",
                    "Image object key was not issued for this candidate event");
        }
    }

    private String boundingBoxJson(CandidateEventCreateRequest.BoundingBox box) {
        return "{\"x\":" + box.x() + ",\"y\":" + box.y() + ",\"width\":" + box.width() + ",\"height\":" + box.height() + "}";
    }
}
