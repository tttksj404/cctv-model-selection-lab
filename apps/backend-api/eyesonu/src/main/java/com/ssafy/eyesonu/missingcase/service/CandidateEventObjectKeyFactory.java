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

    private String eventPrefix(Long mediaServerId, Long cameraId, Long caseId, String eventId) {
        return "realtime/%d/%d/%d/%s".formatted(mediaServerId, cameraId, caseId, digest(eventId));
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
