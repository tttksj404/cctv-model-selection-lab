package com.ssafy.eyesonu.missingcase.controller.device;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobResultResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobResultService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/device/recording-analysis-jobs")
public class DeviceRecordingAnalysisResultController {

    private final RecordingAnalysisJobResultService service;

    public DeviceRecordingAnalysisResultController(RecordingAnalysisJobResultService service) {
        this.service = service;
    }

    @PostMapping(value = "/{jobId}/result", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ApiResponse<RecordingAnalysisJobResultResponse>> complete(
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody CandidateEventCreateRequest request) {
        return ResponseEntity.ok(ApiResponse.of(service.complete(principal, jobId, request)));
    }
}
