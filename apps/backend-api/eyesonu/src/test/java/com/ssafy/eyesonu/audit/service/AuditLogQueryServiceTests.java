package com.ssafy.eyesonu.audit.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.audit.domain.AuditLogRow;
import com.ssafy.eyesonu.audit.domain.AuditLogSortDirection;
import com.ssafy.eyesonu.audit.domain.AuditLogSortField;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogSearchCondition;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;

class AuditLogQueryServiceTests {

    private final AuditLogMapper auditLogMapper = mock(AuditLogMapper.class);
    private final AuditLogQueryService service = new AuditLogQueryService(auditLogMapper);

    @Test
    void appliesFiltersPaginationAndSafeSort() {
        OffsetDateTime from = OffsetDateTime.parse("2026-08-02T10:00:00+09:00");
        OffsetDateTime to = OffsetDateTime.parse("2026-08-02T11:00:00+09:00");
        Instant fromInstant = Instant.parse("2026-08-02T01:00:00Z");
        Instant toInstant = Instant.parse("2026-08-02T02:00:00Z");
        AuditLogRow row = row(12L);
        when(auditLogMapper.countAdminAuditLogs(
                20L, "CASE_STATUS_CHANGED", null, "관리자", fromInstant, toInstant))
                .thenReturn(21L);
        when(auditLogMapper.findAdminPage(
                20L,
                "CASE_STATUS_CHANGED",
                null,
                "관리자",
                fromInstant,
                toInstant,
                AuditLogSortField.CREATED_AT,
                AuditLogSortDirection.ASC,
                10,
                10L))
                .thenReturn(List.of(row));

        AuditLogPageResult result = service.findAll(new AuditLogSearchCondition(
                20L, " CASE_STATUS_CHANGED ", " 관리자 ", from, to, 1, 10, "createdAt,asc"));

        assertEquals(1, result.page());
        assertEquals(10, result.size());
        assertEquals(21L, result.totalElements());
        assertEquals(3, result.totalPages());
        assertEquals("createdAt,asc", result.sort());
        assertEquals(12L, result.logs().getFirst().id());
        assertEquals("Administrator", result.logs().getFirst().adminName());
        verify(auditLogMapper).findAdminPage(
                20L,
                "CASE_STATUS_CHANGED",
                null,
                "관리자",
                fromInstant,
                toInstant,
                AuditLogSortField.CREATED_AT,
                AuditLogSortDirection.ASC,
                10,
                10L);
    }

    @Test
    void emptyPageUsesDefaultsAndSkipsPageQuery() {
        when(auditLogMapper.countAdminAuditLogs(null, null, null, null, null, null)).thenReturn(0L);

        AuditLogPageResult result = service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, 0, 20, null));

        assertEquals(List.of(), result.logs());
        assertEquals(0, result.totalPages());
        assertEquals("createdAt,desc", result.sort());
        verify(auditLogMapper, never()).findAdminPage(
                any(), any(), any(), any(), any(), any(), any(), any(), eq(20), eq(0L));
    }

    @Test
    void rejectsInvalidPageSizePeriodAndSort() {
        assertValidation(() -> service.findAll(new AuditLogSearchCondition(
                null,
                null,
                null,
                OffsetDateTime.parse("2026-08-02T01:00:00Z"),
                OffsetDateTime.parse("2026-08-02T01:00:00Z"),
                0,
                20,
                null)));
        assertValidation(() -> service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, -1, 20, null)));
        assertValidation(() -> service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, 0, 101, null)));
        assertValidation(() -> service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, 0, 20, "detail,desc")));
        assertValidation(() -> service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, 0, 20, "createdAt,sideways")));
    }

    @Test
    void masksSensitiveJsonAndFallsBackToAdminIdDisplayName() {
        AuditLogRow row = new AuditLogRow(
                15L,
                Instant.parse("2026-08-02T01:00:00Z"),
                99L,
                null,
                null,
                "ADMIN_PASSWORD_CHANGE",
                "ADMIN",
                99L,
                "{\"password\":\"secret\",\"safe\":\"visible\"}",
                "{\"apiToken\":\"token-value\"}",
                "{\"photoUrl\":\"https://storage.example/photo.jpg\",\"image\":\"raw-image\",\"ok\":true}");
        when(auditLogMapper.countAdminAuditLogs(null, null, null, null, null, null)).thenReturn(1L);
        when(auditLogMapper.findAdminPage(
                any(), any(), any(), any(), any(), any(), any(), any(), eq(20), eq(0L)))
                .thenReturn(List.of(row));

        AuditLogListResponse response = service.findAll(
                new AuditLogSearchCondition(null, null, null, null, null, 0, 20, null))
                .logs()
                .getFirst();

        assertEquals("99", response.adminName());
        Map<?, ?> before = assertInstanceOf(Map.class, response.beforeValue());
        Map<?, ?> after = assertInstanceOf(Map.class, response.afterValue());
        Map<?, ?> detail = assertInstanceOf(Map.class, response.detail());
        assertEquals("[REDACTED]", before.get("password"));
        assertEquals("visible", before.get("safe"));
        assertEquals("[REDACTED]", after.get("apiToken"));
        assertEquals("[REDACTED]", detail.get("photoUrl"));
        assertEquals("[REDACTED]", detail.get("image"));
    }

    @Test
    void treatsNumericActorAsExactAdminIdFilter() {
        when(auditLogMapper.countAdminAuditLogs(null, null, 255002L, null, null, null))
                .thenReturn(0L);

        service.findAll(new AuditLogSearchCondition(
                null, null, " 255002 ", null, null, 0, 20, null));

        verify(auditLogMapper).countAdminAuditLogs(null, null, 255002L, null, null, null);
    }

    private AuditLogRow row(Long id) {
        return new AuditLogRow(
                id,
                Instant.parse("2026-08-02T01:30:00Z"),
                7L,
                "Administrator",
                20L,
                "CASE_STATUS_CHANGED",
                "CASE",
                20L,
                "{\"status\":\"RECEIVED\"}",
                "{\"status\":\"SEARCHING\"}",
                "{\"reason\":\"Begin search\"}");
    }

    private void assertValidation(Runnable action) {
        ApiException exception = assertThrows(ApiException.class, action::run);
        assertEquals("VALIDATION_ERROR", exception.getCode());
        assertEquals(400, exception.getStatus().value());
    }
}
