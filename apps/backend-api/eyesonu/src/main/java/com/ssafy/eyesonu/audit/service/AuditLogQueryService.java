package com.ssafy.eyesonu.audit.service;

import com.ssafy.eyesonu.audit.domain.AuditLogSortDirection;
import com.ssafy.eyesonu.audit.domain.AuditLogSortField;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogSearchCondition;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Locale;
import org.springframework.http.HttpStatus;
import org.springframework.stereotype.Service;

@Service
public class AuditLogQueryService {

    private static final int MAX_SIZE = 100;
    private static final String DEFAULT_SORT = "createdAt,desc";

    private final AuditLogMapper auditLogMapper;

    public AuditLogQueryService(AuditLogMapper auditLogMapper) {
        this.auditLogMapper = auditLogMapper;
    }

    public AuditLogPageResult findAll(AuditLogSearchCondition condition) {
        validatePage(condition.page(), condition.size());
        ParsedSort sort = parseSort(condition.sort());
        Instant from = toInstant(condition.from());
        Instant to = toInstant(condition.to());
        if (from != null && to != null && !from.isBefore(to)) {
            throw validation("from must be before to");
        }

        Long caseId = condition.caseId();
        String actionType = normalizeOptional(condition.actionType());
        String actor = normalizeOptional(condition.actor());
        long totalElements = auditLogMapper.countAdminAuditLogs(caseId, actionType, actor, from, to);
        long offset = (long) condition.page() * condition.size();
        List<AuditLogListResponse> logs = totalElements == 0
                ? List.of()
                : auditLogMapper.findAdminPage(
                                caseId,
                                actionType,
                                actor,
                                from,
                                to,
                                sort.field(),
                                sort.direction(),
                                condition.size(),
                                offset)
                        .stream()
                        .map(AuditLogListResponse::from)
                        .toList();

        long totalPagesLong = totalElements / condition.size()
                + (totalElements % condition.size() == 0 ? 0 : 1);
        int totalPages = (int) Math.min(Integer.MAX_VALUE, totalPagesLong);
        return new AuditLogPageResult(
                logs,
                condition.page(),
                condition.size(),
                totalElements,
                totalPages,
                sort.externalValue());
    }

    private Instant toInstant(OffsetDateTime value) {
        return value == null ? null : value.toInstant();
    }

    private void validatePage(int page, int size) {
        if (page < 0) {
            throw validation("page must be at least 0");
        }
        if (size < 1 || size > MAX_SIZE) {
            throw validation("size must be between 1 and 100");
        }
    }

    private ParsedSort parseSort(String value) {
        String normalized = normalizeOptional(value);
        if (normalized == null) {
            normalized = DEFAULT_SORT;
        }
        String[] parts = normalized.split(",", -1);
        if (parts.length != 2) {
            throw validation("sort must have the form {field},{direction}");
        }

        AuditLogSortField field = switch (parts[0]) {
            case "createdAt" -> AuditLogSortField.CREATED_AT;
            case "id" -> AuditLogSortField.ID;
            case "actionType" -> AuditLogSortField.ACTION_TYPE;
            case "adminId" -> AuditLogSortField.ADMIN_ID;
            case "caseId" -> AuditLogSortField.CASE_ID;
            default -> throw validation("sort field is not supported");
        };
        AuditLogSortDirection direction = switch (parts[1].toLowerCase(Locale.ROOT)) {
            case "asc" -> AuditLogSortDirection.ASC;
            case "desc" -> AuditLogSortDirection.DESC;
            default -> throw validation("sort direction must be asc or desc");
        };
        return new ParsedSort(field, direction, parts[0] + "," + parts[1].toLowerCase(Locale.ROOT));
    }

    private String normalizeOptional(String value) {
        if (value == null) {
            return null;
        }
        String normalized = value.trim();
        return normalized.isEmpty() ? null : normalized;
    }

    private ApiException validation(String message) {
        return new ApiException(HttpStatus.BAD_REQUEST, "VALIDATION_ERROR", message);
    }

    private record ParsedSort(
            AuditLogSortField field,
            AuditLogSortDirection direction,
            String externalValue) {
    }
}
