package com.ssafy.eyesonu.recording.dto.aiworker;

import java.util.List;

public record AiWorkerEvidenceUploadUrlResponse(
        String schemaVersion,
        Long jobId,
        int attempt,
        long expiresInSeconds,
        List<Upload> uploads) {

    public record Upload(
            String candidateKey,
            String frameObjectKey,
            String frameUploadUrl,
            String cropObjectKey,
            String cropUploadUrl) {
    }
}
