package com.ssafy.eyesonu.recording.controller.admin;

import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobCreateRequest;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/cases/{caseId}/recording-analysis-jobs")
public class AdminRecordingAnalysisJobController {

    private final RecordingAnalysisJobService service;

    public AdminRecordingAnalysisJobController(RecordingAnalysisJobService service) {
        this.service = service;
    }

    @PostMapping
    public ResponseEntity<ApiResponse<RecordingAnalysisJobResponse>> create(
            @PathVariable @Positive Long caseId,
            @Valid @RequestBody RecordingAnalysisJobCreateRequest request,
            @AuthenticationPrincipal AdminPrincipal principal) {
        RecordingAnalysisJobResponse response = service.create(caseId, request, principal.getAdminId());
        return ResponseEntity.created(URI.create(
                        "/api/v1/admin/cases/" + caseId + "/recording-analysis-jobs/" + response.jobId()))
                .body(ApiResponse.of(response));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<RecordingAnalysisJobResponse>>> findAll(
            @PathVariable @Positive Long caseId) {
        return ResponseEntity.ok(ApiResponse.of(service.findAll(caseId)));
    }

    @PostMapping("/{jobId}/cancel")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobResponse>> cancel(
            @PathVariable @Positive Long caseId,
            @PathVariable @Positive Long jobId,
            @AuthenticationPrincipal AdminPrincipal principal) {
        return ResponseEntity.ok(ApiResponse.of(service.cancel(caseId, jobId, principal.getAdminId())));
    }

    @PostMapping("/{jobId}/retry")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobResponse>> retry(
            @PathVariable @Positive Long caseId,
            @PathVariable @Positive Long jobId,
            @AuthenticationPrincipal AdminPrincipal principal) {
        return ResponseEntity.accepted().body(ApiResponse.of(service.retry(caseId, jobId, principal.getAdminId())));
    }

    @GetMapping("/{jobId}")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobResponse>> findById(
            @PathVariable @Positive Long caseId,
            @PathVariable @Positive Long jobId) {
        return ResponseEntity.ok(ApiResponse.of(service.findById(caseId, jobId)));
    }
}
