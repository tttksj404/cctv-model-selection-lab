package com.ssafy.eyesonu.recording.service;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.domain.AnalysisJob;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventObjectKeyFactory;
import com.ssafy.eyesonu.storage.StorageObjectUnavailableException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import java.util.HashSet;
import java.util.List;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class RecordingAnalysisUploadUrlService {

    private final CandidateEventObjectKeyFactory objectKeyFactory;
    private final StorageObjectUrlSigner urlSigner;
    private final MinioProperties minioProperties;
    private final RecordingAnalysisJobClaimService claimService;

    public RecordingAnalysisUploadUrlService(
            CandidateEventObjectKeyFactory objectKeyFactory,
            StorageObjectUrlSigner urlSigner,
            MinioProperties minioProperties,
            RecordingAnalysisJobClaimService claimService) {
        this.objectKeyFactory = objectKeyFactory;
        this.urlSigner = urlSigner;
        this.minioProperties = minioProperties;
        this.claimService = claimService;
    }

    public RecordingAnalysisUploadUrlCreateResponse create(
            Long jobId,
            String workerId,
            String claimToken,
            RecordingAnalysisUploadUrlCreateRequest request) {
        if (request == null || request.candidates() == null || request.candidates().isEmpty()) {
            throw new ApiException(HttpStatus.BAD_REQUEST,
                    "VALIDATION_ERROR", "At least one candidate is required.");
        }

        AnalysisJob job = claimService.requireActiveWorkerJob(jobId, workerId, claimToken);
        validateUniqueTrackIds(request);

        int attempt = job.getRetryCount() + 1;
        List<RecordingAnalysisUploadUrlCreateResponse.CandidateUpload> uploads = request.candidates().stream()
                .map(candidate -> createCandidateUpload(job, attempt, candidate))
                .toList();
        return new RecordingAnalysisUploadUrlCreateResponse(
                attempt, uploads, minioProperties.getPresignedUrlExpiry().toSeconds());
    }

    private RecordingAnalysisUploadUrlCreateResponse.CandidateUpload createCandidateUpload(
            AnalysisJob job, int attempt, RecordingAnalysisUploadUrlCreateRequest.Candidate candidate) {
        String frameKey = objectKeyFactory.analysisFrameKey(
                job.getId(), attempt, candidate.trackId(), candidate.frameContentType());
        String cropKey = objectKeyFactory.analysisCropKey(
                job.getId(), attempt, candidate.trackId(), candidate.cropContentType());
        return new RecordingAnalysisUploadUrlCreateResponse.CandidateUpload(
                candidate.trackId(),
                new RecordingAnalysisUploadUrlCreateResponse.Upload(
                        frameKey, sign(frameKey), candidate.frameContentType()),
                new RecordingAnalysisUploadUrlCreateResponse.Upload(
                        cropKey, sign(cropKey), candidate.cropContentType()));
    }

    private String sign(String objectKey) {
        try {
            return urlSigner.createPutUrl(objectKey);
        } catch (StorageObjectUnavailableException exception) {
            throw new ApiException(HttpStatus.SERVICE_UNAVAILABLE,
                    "STORAGE_UNAVAILABLE", "Image upload URL could not be created.");
        }
    }

    private void validateUniqueTrackIds(RecordingAnalysisUploadUrlCreateRequest request) {
        Set<String> trackIds = new HashSet<>();
        if (request.candidates().stream().anyMatch(candidate -> !trackIds.add(candidate.trackId()))) {
            throw new ApiException(HttpStatus.BAD_REQUEST,
                    "VALIDATION_ERROR", "trackId must be unique.");
        }
    }
}
