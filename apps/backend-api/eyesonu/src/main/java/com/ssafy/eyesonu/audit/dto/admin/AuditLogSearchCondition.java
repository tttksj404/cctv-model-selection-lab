package com.ssafy.eyesonu.audit.dto.admin;

import java.time.OffsetDateTime;

public record AuditLogSearchCondition(
        Long caseId,
        String actionType,
        String actor,
        OffsetDateTime from,
        OffsetDateTime to,
        int page,
        int size,
        String sort) {
}
