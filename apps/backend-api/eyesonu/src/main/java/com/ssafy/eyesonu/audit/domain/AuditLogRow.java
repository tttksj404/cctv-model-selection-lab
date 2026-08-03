package com.ssafy.eyesonu.audit.domain;

import java.time.Instant;

public record AuditLogRow(
        Long id,
        Instant createdAt,
        Long adminId,
        String adminName,
        Long caseId,
        String actionType,
        String targetType,
        Long targetId,
        String beforeValue,
        String afterValue,
        String detail) {
}
