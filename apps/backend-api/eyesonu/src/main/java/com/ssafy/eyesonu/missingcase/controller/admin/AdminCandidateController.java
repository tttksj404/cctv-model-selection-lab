package com.ssafy.eyesonu.missingcase.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateDetailResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateListResponse;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateSearchCondition;
import com.ssafy.eyesonu.missingcase.dto.admin.AdminCandidateReviewRequest;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateReviewService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import jakarta.validation.Valid;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import com.ssafy.eyesonu.missingcase.service.AdminCandidatePageResult;
import com.ssafy.eyesonu.missingcase.service.AdminCandidateQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.Instant;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.CacheControl;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/candidates")
public class AdminCandidateController {
    private final AdminCandidateQueryService queryService;
    private final AdminCandidateReviewService reviewService;

    public AdminCandidateController(AdminCandidateQueryService queryService, AdminCandidateReviewService reviewService) {
        this.queryService = queryService;
        this.reviewService = reviewService;
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
            @RequestParam(defaultValue = "lastDetectedAt,desc") String sort,
            @RequestHeader(value = HttpHeaders.IF_NONE_MATCH, required = false) String ifNoneMatch) {
        AdminCandidateSearchCondition condition = new AdminCandidateSearchCondition(
                caseId, cameraId, reviewStatus, detectedFrom, detectedTo, page, size, sort);
        String etag = buildEtag(condition, queryService.findLastModified());
        CacheControl cacheControl = CacheControl.noCache().cachePrivate().mustRevalidate();
        if (matches(ifNoneMatch, etag)) {
            return ResponseEntity.status(HttpStatus.NOT_MODIFIED)
                    .eTag(etag)
                    .cacheControl(cacheControl)
                    .build();
        }

        AdminCandidatePageResult result = queryService.findAll(condition);
        return ResponseEntity.ok()
                .eTag(etag)
                .cacheControl(cacheControl)
                .body(PagedApiResponse.of(result.candidates(), new PageMeta(
                        result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort())));
    }

    private String buildEtag(AdminCandidateSearchCondition condition, Instant lastModified) {
        String version = lastModified == null ? "empty" : lastModified.toString();
        String query = String.join("|",
                String.valueOf(condition.caseId()), String.valueOf(condition.cameraId()),
                String.valueOf(condition.reviewStatus()), String.valueOf(condition.detectedFrom()),
                String.valueOf(condition.detectedTo()), String.valueOf(condition.page()),
                String.valueOf(condition.size()), condition.sort().replace(',', '_'));
        return "\"admin-candidates-" + version + "-" + query + "\"";
    }

    private boolean matches(String ifNoneMatch, String etag) {
        if (ifNoneMatch == null) return false;
        for (String candidate : ifNoneMatch.split(",")) {
            String normalized = candidate.trim();
            if ("*".equals(normalized) || etag.equals(normalized)) return true;
        }
        return false;
    }

    @GetMapping("/{candidateId}")
    public ResponseEntity<ApiResponse<AdminCandidateDetailResponse>> findById(
            @PathVariable @Positive Long candidateId) {
        return ResponseEntity.ok(ApiResponse.of(queryService.findById(candidateId)));
    }

    @org.springframework.web.bind.annotation.PatchMapping("/{candidateId}/review")
    public ResponseEntity<ApiResponse<AdminCandidateDetailResponse>> review(
            @PathVariable @Positive Long candidateId,
            @Valid @org.springframework.web.bind.annotation.RequestBody AdminCandidateReviewRequest request,
            @AuthenticationPrincipal AdminPrincipal principal) {
        return ResponseEntity.ok(ApiResponse.of(reviewService.review(candidateId, request, principal.getAdminId())));
    }
}
