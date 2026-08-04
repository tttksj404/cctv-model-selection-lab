package com.ssafy.eyesonu.missingcase.service;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.security.NoSuchAlgorithmException;
import java.util.HexFormat;
import org.springframework.stereotype.Component;

@Component
public class CandidateEventObjectKeyFactory {

    public String frameKey(Long mediaServerId, Long cameraId, Long caseId, String eventId, String contentType) {
        return eventPrefix(mediaServerId, cameraId, caseId, eventId) + "/frame." + extension(contentType);
    }

    public String cropKey(Long mediaServerId, Long cameraId, Long caseId, String eventId,
                          String trackId, String contentType) {
        return eventPrefix(mediaServerId, cameraId, caseId, eventId)
                + "/crops/" + digest(trackId) + "." + extension(contentType);
    }

    public boolean matchesFrameKey(Long mediaServerId, Long cameraId, Long caseId,
                                   String eventId, String objectKey) {
        return frameKey(mediaServerId, cameraId, caseId, eventId, "image/jpeg").equals(objectKey)
                || frameKey(mediaServerId, cameraId, caseId, eventId, "image/png").equals(objectKey);
    }

    public boolean matchesCropKey(Long mediaServerId, Long cameraId, Long caseId,
                                  String eventId, String trackId, String objectKey) {
        return cropKey(mediaServerId, cameraId, caseId, eventId, trackId, "image/jpeg").equals(objectKey)
                || cropKey(mediaServerId, cameraId, caseId, eventId, trackId, "image/png").equals(objectKey);
    }

    public boolean matchesAnalysisFrameKey(Long jobId, int attempt, String objectKey) {
        return validAnalysisDescendant(jobId, attempt, "frames", objectKey);
    }

    public boolean matchesAnalysisCropKey(Long jobId, int attempt, String objectKey) {
        return validAnalysisDescendant(jobId, attempt, "crops", objectKey);
    }

    public boolean matchesIssuedAnalysisFrameKey(
            Long jobId, int attempt, String trackId, String objectKey) {
        return analysisFrameKey(jobId, attempt, trackId, "image/jpeg").equals(objectKey)
                || analysisFrameKey(jobId, attempt, trackId, "image/png").equals(objectKey);
    }

    public boolean matchesIssuedAnalysisCropKey(
            Long jobId, int attempt, String trackId, String objectKey) {
        return analysisCropKey(jobId, attempt, trackId, "image/jpeg").equals(objectKey)
                || analysisCropKey(jobId, attempt, trackId, "image/png").equals(objectKey);
    }

    public String analysisFrameKey(Long jobId, int attempt, String trackId, String contentType) {
        return analysisKey(jobId, attempt, "frames", trackId, contentType);
    }

    public String analysisCropKey(Long jobId, int attempt, String trackId, String contentType) {
        return analysisKey(jobId, attempt, "crops", trackId, contentType);
    }

    private String eventPrefix(Long mediaServerId, Long cameraId, Long caseId, String eventId) {
        return "realtime/%d/%d/%d/%s".formatted(mediaServerId, cameraId, caseId, digest(eventId));
    }

    private boolean validAnalysisDescendant(Long jobId, int attempt, String directory, String objectKey) {
        if (jobId == null || attempt < 1 || objectKey == null) {
            return false;
        }
        String prefix = "analysis/analysis-%d/attempt-%d/%s/".formatted(jobId, attempt, directory);
        return objectKey.startsWith(prefix)
                && objectKey.length() > prefix.length()
                && !objectKey.contains("\\")
                && !objectKey.contains("..")
                && objectKey.chars().noneMatch(Character::isISOControl);
    }

    private String analysisKey(Long jobId, int attempt, String directory, String name, String contentType) {
        if (jobId == null || attempt < 1 || name == null || name.isBlank()) {
            throw new IllegalArgumentException("Analysis object key inputs are invalid");
        }
        return "analysis/analysis-%d/attempt-%d/%s/%s.%s".formatted(
                jobId, attempt, directory, digest(name), extension(contentType));
    }

    private String extension(String contentType) {
        return switch (contentType) {
            case "image/jpeg" -> "jpg";
            case "image/png" -> "png";
            default -> throw new IllegalArgumentException("Unsupported image content type");
        };
    }

    private String digest(String value) {
        try {
            MessageDigest digest = MessageDigest.getInstance("SHA-256");
            return HexFormat.of().formatHex(digest.digest(value.getBytes(StandardCharsets.UTF_8)));
        } catch (NoSuchAlgorithmException exception) {
            throw new IllegalStateException("SHA-256 is not available", exception);
        }
    }
}
