package com.ssafy.eyesonu.audit.controller.admin;

import com.ssafy.eyesonu.audit.controller.docs.AdminAuditLogControllerDocs;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import com.ssafy.eyesonu.audit.dto.admin.AuditLogSearchCondition;
import com.ssafy.eyesonu.audit.service.AuditLogPageResult;
import com.ssafy.eyesonu.audit.service.AuditLogQueryService;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/audit-logs")
public class AdminAuditLogController implements AdminAuditLogControllerDocs {

    private final AuditLogQueryService queryService;

    public AdminAuditLogController(AuditLogQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping
    @Override
    public ResponseEntity<PagedApiResponse<List<AuditLogListResponse>>> findAll(
            @RequestParam(required = false) @Positive Long caseId,
            @RequestParam(required = false) String actionType,
            @RequestParam(required = false) String actor,
            @RequestParam(required = false)
                    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime from,
            @RequestParam(required = false)
                    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime to,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
            @RequestParam(defaultValue = "createdAt,desc") String sort) {
        AuditLogPageResult result = queryService.findAll(
                new AuditLogSearchCondition(caseId, actionType, actor, from, to, page, size, sort));
        PageMeta meta = new PageMeta(
                result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort());
        return ResponseEntity.ok(PagedApiResponse.of(result.logs(), meta));
    }
}
