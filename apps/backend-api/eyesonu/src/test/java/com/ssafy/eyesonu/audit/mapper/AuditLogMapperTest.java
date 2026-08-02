package com.ssafy.eyesonu.audit.mapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertEquals;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.audit.domain.AuditLogRow;
import com.ssafy.eyesonu.audit.domain.AuditLogSortDirection;
import com.ssafy.eyesonu.audit.domain.AuditLogSortField;
import java.time.Instant;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest(properties = "spring.flyway.enabled=true")
@ActiveProfiles("test")
@Import(TestDatabaseConfiguration.class)
@Transactional
@Sql(
        scripts = "/audit-log-fixture.sql",
        config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.INFERRED))
class AuditLogMapperTest {

    @Autowired
    private AuditLogMapper auditLogMapper;

    @Test
    void appliesHalfOpenTimeRangeAndResolvesAdminDisplayName() {
        List<AuditLogRow> rows = auditLogMapper.findAdminPage(
                null,
                null,
                null,
                null,
                Instant.parse("2026-08-02T01:00:00Z"),
                Instant.parse("2026-08-02T03:00:00Z"),
                AuditLogSortField.CREATED_AT,
                AuditLogSortDirection.ASC,
                20,
                0);

        assertThat(rows).extracting(AuditLogRow::id).containsExactly(255001L, 255002L);
        assertEquals("Audit Admin One", rows.getFirst().adminName());
        assertThat(rows.getFirst().beforeValue()).contains("\"status\"", "RECEIVED");
        assertThat(rows.getFirst().detail()).contains("\"reason\"", "begin");
    }

    @Test
    void appliesCaseActionActorFiltersAndPagination() {
        assertEquals(
                2L,
                auditLogMapper.countAdminAuditLogs(255001L, null, null, null, null, null));
        assertEquals(
                1L,
                auditLogMapper.countAdminAuditLogs(null, "ADMIN_LOGIN_SUCCESS", 255002L, null, null, null));
        assertEquals(
                2L,
                auditLogMapper.countAdminAuditLogs(null, null, null, "audit-admin-1", null, null));

        List<AuditLogRow> rows = auditLogMapper.findAdminPage(
                null,
                null,
                null,
                null,
                null,
                null,
                AuditLogSortField.CREATED_AT,
                AuditLogSortDirection.DESC,
                1,
                1);

        assertThat(rows).extracting(AuditLogRow::id).containsExactly(255002L);
    }
}
