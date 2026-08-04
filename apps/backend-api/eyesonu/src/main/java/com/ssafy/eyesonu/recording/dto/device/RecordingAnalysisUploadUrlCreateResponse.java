package com.ssafy.eyesonu.recording.dto.device;

import java.util.List;

public record RecordingAnalysisUploadUrlCreateResponse(
        int attempt,
        List<CandidateUpload> candidates,
        long expiresInSeconds) {

    public record CandidateUpload(String trackId, Upload frame, Upload crop) {
    }

    public record Upload(String objectKey, String uploadUrl, String contentType) {
    }
}
