package com.ssafy.eyesonu.missingcase.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateSearchCondition;
import com.ssafy.eyesonu.missingcase.service.AdminCandidatePageResult;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/candidates")
public class AdminCandidateController {
    private final AdminCandidateQueryService queryService;

    public AdminCandidateController(AdminCandidateQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping
    public ResponseEntity<PagedApiResponse<List<AdminCandidateListResponse>>> findAll(
            @RequestParam(required = false) @Positive Long caseId,
            @RequestParam(required = false) @Positive Long cameraId,
            @RequestParam(required = false) String reviewStatus,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime detectedFrom,
            @RequestParam(required = false) @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime detectedTo,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
            @RequestParam(defaultValue = "lastDetectedAt,desc") String sort) {
        AdminCandidatePageResult result = queryService.findAll(new AdminCandidateSearchCondition(
                caseId, cameraId, reviewStatus, detectedFrom, detectedTo, page, size, sort));
        return ResponseEntity.ok(PagedApiResponse.of(result.candidates(), new PageMeta(
                result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort())));
    }

    @GetMapping("/{candidateId}")
    public ResponseEntity<ApiResponse<AdminCandidateDetailResponse>> findById(
            @PathVariable @Positive Long candidateId) {
        return ResponseEntity.ok(ApiResponse.of(queryService.findById(candidateId)));
    }
}
