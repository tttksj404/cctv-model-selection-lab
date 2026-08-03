package com.ssafy.eyesonu.missingcase.controller.device;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventSubmissionService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/device")
public class DeviceCandidateEventController {
    private final CandidateEventSubmissionService submissionService;

    public DeviceCandidateEventController(CandidateEventSubmissionService submissionService) {
        this.submissionService = submissionService;
    }

    @PostMapping(value = "/candidate-events", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ApiResponse<CandidateEventCreateResponse>> create(
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @Valid @RequestBody CandidateEventCreateRequest request) {
        CandidateEventCreateResponse response = submissionService.create(principal, request);
        return ResponseEntity.status(response.duplicate() ? HttpStatus.OK : HttpStatus.CREATED)
                .body(ApiResponse.of(response));
    }
}
