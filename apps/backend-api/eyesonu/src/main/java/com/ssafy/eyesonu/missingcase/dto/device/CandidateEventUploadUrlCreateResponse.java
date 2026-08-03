package com.ssafy.eyesonu.missingcase.dto.device;

import java.util.List;

public record CandidateEventUploadUrlCreateResponse(
        Upload frame,
        List<DetectionUpload> detections,
        long expiresInSeconds) {

    public record Upload(String objectKey, String uploadUrl, String contentType) {
    }

    public record DetectionUpload(String trackId, String objectKey, String uploadUrl, String contentType) {
    }
}
