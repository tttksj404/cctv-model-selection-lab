package com.ssafy.eyesonu.recording.controller.aiworker;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerClaimResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerCompleteRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerFailRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatRequest;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerHeartbeatResponse;
import com.ssafy.eyesonu.recording.dto.aiworker.AiWorkerJobStatusResponse;
import com.ssafy.eyesonu.recording.service.AiWorkerAuthenticationService;
import com.ssafy.eyesonu.recording.service.AiWorkerJobService;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Positive;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/ai-worker/jobs")
public class AiWorkerJobController {

    public static final String AUTH_HEADER = "X-AI-Worker-Key";

    private final AiWorkerAuthenticationService authenticationService;
    private final AiWorkerJobService service;

    public AiWorkerJobController(
            AiWorkerAuthenticationService authenticationService,
            AiWorkerJobService service) {
        this.authenticationService = authenticationService;
        this.service = service;
    }

    @PostMapping("/claim")
    public ResponseEntity<ApiResponse<AiWorkerClaimResponse>> claim(
            @Valid @RequestBody AiWorkerClaimRequest request,
            @RequestHeader(value = AUTH_HEADER, required = false) String workerKey) {
        authenticationService.requireValidKey(workerKey);
        return ResponseEntity.ok(ApiResponse.of(service.claim(request)));
    }

    @PostMapping("/{jobId}/heartbeat")
    public ResponseEntity<ApiResponse<AiWorkerHeartbeatResponse>> heartbeat(
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody AiWorkerHeartbeatRequest request,
            @RequestHeader(value = AUTH_HEADER, required = false) String workerKey) {
        authenticationService.requireValidKey(workerKey);
        return ResponseEntity.ok(ApiResponse.of(service.heartbeat(jobId, request)));
    }

    @PostMapping("/{jobId}/complete")
    public ResponseEntity<ApiResponse<AiWorkerJobStatusResponse>> complete(
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody AiWorkerCompleteRequest request,
            @RequestHeader(value = AUTH_HEADER, required = false) String workerKey) {
        authenticationService.requireValidKey(workerKey);
        return ResponseEntity.ok(ApiResponse.of(service.complete(jobId, request)));
    }

    @PostMapping("/{jobId}/fail")
    public ResponseEntity<ApiResponse<AiWorkerJobStatusResponse>> fail(
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody AiWorkerFailRequest request,
            @RequestHeader(value = AUTH_HEADER, required = false) String workerKey) {
        authenticationService.requireValidKey(workerKey);
        return ResponseEntity.ok(ApiResponse.of(service.fail(jobId, request)));
    }
}
