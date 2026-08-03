package com.ssafy.eyesonu.audit.dto.admin;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.ssafy.eyesonu.audit.domain.AuditLogRow;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

public record AuditLogListResponse(
        Long id,
        Instant createdAt,
        Long adminId,
        String adminName,
        Long caseId,
        String actionType,
        String targetType,
        Long targetId,
        Object beforeValue,
        Object afterValue,
        Object detail) {

    private static final ObjectMapper JSON_MAPPER = new ObjectMapper();
    private static final String REDACTED = "[REDACTED]";

    public static AuditLogListResponse from(AuditLogRow row) {
        return new AuditLogListResponse(
                row.id(),
                row.createdAt(),
                row.adminId(),
                displayAdminName(row.adminId(), row.adminName()),
                row.caseId(),
                row.actionType(),
                row.targetType(),
                row.targetId(),
                safeJson(row.beforeValue()),
                safeJson(row.afterValue()),
                safeJson(row.detail()));
    }

    private static String displayAdminName(Long adminId, String adminName) {
        if (adminName != null && !adminName.isBlank()) {
            return adminName;
        }
        return adminId == null ? null : String.valueOf(adminId);
    }

    private static Object safeJson(String json) {
        if (json == null) {
            return null;
        }
        if (json.isBlank()) {
            return Map.of();
        }
        try {
            return sanitize(JSON_MAPPER.readValue(json, Object.class));
        }
        catch (JsonProcessingException exception) {
            return Map.of("redacted", true);
        }
    }

    private static Object sanitize(Object value) {
        if (value instanceof Map<?, ?> map) {
            Map<String, Object> sanitized = new LinkedHashMap<>();
            map.forEach((key, mapValue) -> {
                String name = String.valueOf(key);
                sanitized.put(name, isSensitiveKey(name) ? REDACTED : sanitize(mapValue));
            });
            return sanitized;
        }
        if (value instanceof List<?> list) {
            List<Object> sanitized = new ArrayList<>(list.size());
            list.forEach(item -> sanitized.add(sanitize(item)));
            return sanitized;
        }
        return value;
    }

    private static boolean isSensitiveKey(String key) {
        String normalized = key.toLowerCase(Locale.ROOT).replaceAll("[^a-z0-9]", "");
        return normalized.contains("password")
                || normalized.contains("token")
                || normalized.contains("secret")
                || normalized.contains("credential")
                || normalized.contains("authorization")
                || normalized.contains("cookie")
                || normalized.contains("fingerprint")
                || normalized.contains("s3key")
                || normalized.contains("streamurl")
                || normalized.contains("rtspurl")
                || normalized.contains("base64")
                || normalized.equals("image")
                || normalized.equals("imagedata")
                || normalized.equals("photo")
                || normalized.equals("photodata")
                || normalized.equals("photourl")
                || normalized.equals("imageurl");
    }
}
