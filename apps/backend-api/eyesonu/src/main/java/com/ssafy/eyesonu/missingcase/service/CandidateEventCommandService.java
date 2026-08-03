package com.ssafy.eyesonu.missingcase.service;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.domain.CandidateAggregate;
import com.ssafy.eyesonu.missingcase.domain.CandidateEvent;
import com.ssafy.eyesonu.missingcase.domain.CandidateEventDetection;
import com.ssafy.eyesonu.missingcase.domain.CandidateSourceContext;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.mapper.CandidateEventMapper;
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
    private final CandidateEventMapper mapper;
    private final CaseQueryService caseQueryService;
    private final CandidateEventAccessValidator accessValidator;

    public CandidateEventCommandService(CandidateEventMapper mapper,
                                        CaseQueryService caseQueryService,
                                        CandidateEventAccessValidator accessValidator) {
        this.mapper = mapper;
        this.caseQueryService = caseQueryService;
        this.accessValidator = accessValidator;
    }

    @Transactional
    public CandidateEventCreateResponse createRecordingAnalysis(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request,
            Long expectedCameraId,
            Long analysisJobId,
            Long recordingId) {
        Camera camera = accessValidator.validateCameraAccess(principal, request);
        return create(request, expectedCameraId, camera,
                CandidateSourceContext.recordingAnalysis(analysisJobId, recordingId));
    }

    @Transactional
    public CandidateEventCreateResponse createValidatedRealtime(
            MediaServerPrincipal principal,
            CandidateEventCreateRequest request,
            Camera camera) {
        if (principal == null || camera == null
                || !Objects.equals(camera.mediaServerId(), principal.mediaServerId())
                || !Objects.equals(camera.cameraCode(), request.cameraCode())) {
            throw new ApiException(HttpStatus.FORBIDDEN,
                    "ACCESS_DENIED", "Validated camera context does not match the request");
        }
        return create(request, null, camera,
                CandidateSourceContext.realtime(request.caseId(), camera.id()));
    }

    private CandidateEventCreateResponse create(
            CandidateEventCreateRequest request,
            Long expectedCameraId,
            Camera camera,
            CandidateSourceContext source) {
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
        CandidateEvent existing = mapper.findEventByEventId(request.eventId());
        if (existing != null) return duplicateResult(existing, request, camera.id(), source);

        CandidateEvent event = new CandidateEvent();
        event.setEventId(request.eventId());
        event.setCaseId(request.caseId());
        event.setCameraId(camera.id());
        event.setSourceType(source.sourceType());
        event.setAnalysisJobId(source.analysisJobId());
        event.setRecordingId(source.recordingId());
        event.setDetectedAt(request.detectedAt().toInstant());
        event.setFrameObjectKey(request.frameObjectKey());
        int eventInserted = mapper.insertEvent(event);
        if (eventInserted == 0) {
            CandidateEvent concurrent = mapper.findEventByEventId(request.eventId());
            if (concurrent == null) {
                throw new ApiException(HttpStatus.INTERNAL_SERVER_ERROR,
                        "EVENT_ID_UPSERT_FAILED", "Event could not be loaded after upsert");
            }
            return duplicateResult(concurrent, request, camera.id(), source);
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
            CandidateAggregate candidate = newCandidate(request, camera.id(), input, boundingBox, source);
            int candidateInserted = mapper.insertCandidate(candidate);
            if (candidateInserted == 0) {
                candidate = mapper.findCandidateForUpdate(source.dedupeScope(), input.trackId());
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
                                                         Long cameraId,
                                                         CandidateSourceContext source) {
        List<CandidateEventDetection> stored = mapper.findDetectionsByEventId(request.eventId());
        boolean same = Objects.equals(existing.getCaseId(), request.caseId())
                && Objects.equals(existing.getCameraId(), cameraId)
                && existing.getSourceType() == source.sourceType()
                && Objects.equals(existing.getAnalysisJobId(), source.analysisJobId())
                && Objects.equals(existing.getRecordingId(), source.recordingId())
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
                                             CandidateEventCreateRequest.Detection input, String box,
                                             CandidateSourceContext source) {
        CandidateAggregate candidate = new CandidateAggregate();
        candidate.setCaseId(request.caseId()); candidate.setCameraId(cameraId);
        candidate.setSourceType(source.sourceType()); candidate.setAnalysisJobId(source.analysisJobId());
        candidate.setRecordingId(source.recordingId()); candidate.setDedupeScope(source.dedupeScope());
        candidate.setTrackId(input.trackId());
        candidate.setFirstDetectedAt(request.detectedAt().toInstant()); candidate.setLastDetectedAt(request.detectedAt().toInstant());
        candidate.setBestSimilarity(input.similarity()); candidate.setAverageSimilarity(input.similarity());
        candidate.setDetectionCount(1); candidate.setSimilarity(input.similarity()); candidate.setCropObjectKey(input.cropObjectKey());
        candidate.setFrameObjectKey(request.frameObjectKey()); candidate.setBoundingBox(box);
        return candidate;
    }

    private String boundingBoxJson(CandidateEventCreateRequest.BoundingBox box) {
        return "{\"x\":" + box.x() + ",\"y\":" + box.y() + ",\"width\":" + box.width() + ",\"height\":" + box.height() + "}";
    }
}
