package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.missingcase.service.CandidateEventStorageValidator;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingAnalysisResultStorageValidator {

    private final CandidateEventObjectKeyFactory objectKeyFactory;
    private final CandidateEventStorageValidator storageValidator;

    public RecordingAnalysisResultStorageValidator(
            CandidateEventObjectKeyFactory objectKeyFactory,
            CandidateEventStorageValidator storageValidator) {
        this.objectKeyFactory = objectKeyFactory;
        this.storageValidator = storageValidator;
    }

    public void verify(AnalysisJob job, RecordingAnalysisBatchResultRequest request) {
        int attempt = job.getRetryCount() + 1;
        for (RecordingAnalysisBatchResultRequest.Candidate candidate : request.candidates()) {
            if (!objectKeyFactory.matchesAnalysisFrameKey(job.getId(), attempt, candidate.frameObjectKey())
                    || !objectKeyFactory.matchesAnalysisCropKey(job.getId(), attempt, candidate.cropObjectKey())) {
                throw new ApiException(HttpStatus.BAD_REQUEST, "INVALID_UPLOAD_OBJECT_KEY",
                        "Image object key does not belong to this recording analysis attempt.");
            }
            storageValidator.verify(toStorageRequest(job, candidate));
        }
    }

    private CandidateEventCreateRequest toStorageRequest(
            AnalysisJob job, RecordingAnalysisBatchResultRequest.Candidate candidate) {
        return new CandidateEventCreateRequest(
                job.getCaseId(), "storage-validation", "storage-validation", candidate.detectedAt(),
                candidate.frameObjectKey(), List.of(new CandidateEventCreateRequest.Detection(
                        candidate.trackId(), candidate.similarity(), candidate.cropObjectKey(),
                        candidate.boundingBox().toCandidateBoundingBox())));
    }
}
