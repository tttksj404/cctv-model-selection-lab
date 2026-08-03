package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.domain.AuditLogRow;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogSearchCondition;
import com.ssafy.eyesonu.audit.controller.admin.AdminAuditLogController;
import com.ssafy.eyesonu.audit.service.AuditLogPageResult;
import com.ssafy.eyesonu.audit.service.AuditLogQueryService;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminAuditLogController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AdminAuditLogApiTests {

    private static final AdminPrincipal ADMIN = new AdminPrincipal(1L, "admin");

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private AdminMapper adminMapper;

    @MockitoBean
    private AuditService auditService;

    @MockitoBean
    private MediaServerAuthenticationService mediaServerAuthenticationService;

    @MockitoBean
    private AuditLogQueryService queryService;

    @BeforeEach
    void activeAdmin() {
        when(adminMapper.findById(1L))
                .thenReturn(Optional.of(new Admin(1L, "admin", "hash", "Administrator")));
    }

    @Test
    void auditLogListRequiresAdminAuthentication() throws Exception {
        mockMvc.perform(get("/api/v1/admin/audit-logs"))
                .andExpect(status().isUnauthorized())
                .andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
    }

    @Test
    void auditLogListUsesPagedResponseAndForwardsAllFilters() throws Exception {
        OffsetDateTime from = OffsetDateTime.parse("2026-08-02T10:00:00+09:00");
        OffsetDateTime to = OffsetDateTime.parse("2026-08-02T11:00:00+09:00");
        AuditLogSearchCondition condition = new AuditLogSearchCondition(
                20L, "CASE_STATUS_CHANGED", "Administrator", from, to, 1, 10, "createdAt,asc");
        AuditLogListResponse response = AuditLogListResponse.from(row());
        when(queryService.findAll(eq(condition)))
                .thenReturn(new AuditLogPageResult(List.of(response), 1, 10, 11L, 2, "createdAt,asc"));

        mockMvc.perform(get("/api/v1/admin/audit-logs")
                        .with(adminAuthentication())
                        .param("caseId", "20")
                        .param("actionType", "CASE_STATUS_CHANGED")
                        .param("actor", "Administrator")
                        .param("from", from.toString())
                        .param("to", to.toString())
                        .param("page", "1")
                        .param("size", "10")
                        .param("sort", "createdAt,asc"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data[0].id").value(15))
                .andExpect(jsonPath("$.data[0].adminName").value("Administrator"))
                .andExpect(jsonPath("$.data[0].beforeValue.status").value("RECEIVED"))
                .andExpect(jsonPath("$.data[0].afterValue.status").value("SEARCHING"))
                .andExpect(jsonPath("$.data[0].password").doesNotExist())
                .andExpect(jsonPath("$.meta.page").value(1))
                .andExpect(jsonPath("$.meta.totalElements").value(11))
                .andExpect(jsonPath("$.meta.sort").value("createdAt,asc"));

        verify(queryService).findAll(eq(condition));
    }

    @Test
    void emptyAuditLogListReturnsEmptyPagedData() throws Exception {
        AuditLogSearchCondition condition = new AuditLogSearchCondition(
                null, null, null, null, null, 0, 20, "createdAt,desc");
        when(queryService.findAll(eq(condition)))
                .thenReturn(new AuditLogPageResult(List.of(), 0, 20, 0L, 0, "createdAt,desc"));

        mockMvc.perform(get("/api/v1/admin/audit-logs").with(adminAuthentication()))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$.data").isEmpty())
                .andExpect(jsonPath("$.meta.totalElements").value(0));
    }

    @Test
    void caseIdMustBePositive() throws Exception {
        mockMvc.perform(get("/api/v1/admin/audit-logs")
                        .with(adminAuthentication())
                        .param("caseId", "0"))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));
    }

    private RequestPostProcessor adminAuthentication() {
        return authentication(new UsernamePasswordAuthenticationToken(
                ADMIN, null, ADMIN.getAuthorities()));
    }

    private AuditLogRow row() {
        return new AuditLogRow(
                15L,
                Instant.parse("2026-08-02T01:30:00Z"),
                1L,
                "Administrator",
                20L,
                "CASE_STATUS_CHANGED",
                "CASE",
                20L,
                "{\"status\":\"RECEIVED\"}",
                "{\"status\":\"SEARCHING\"}",
                "{\"reason\":\"Begin search\"}");
    }
}
