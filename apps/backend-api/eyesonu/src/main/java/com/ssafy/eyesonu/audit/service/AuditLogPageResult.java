package com.ssafy.eyesonu.audit.service;

import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import java.util.List;

public record AuditLogPageResult(
        List<AuditLogListResponse> logs,
        int page,
        int size,
        long totalElements,
        int totalPages,
        String sort) {
}
