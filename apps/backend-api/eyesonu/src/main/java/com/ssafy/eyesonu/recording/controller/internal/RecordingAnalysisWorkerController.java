package com.ssafy.eyesonu.recording.controller.internal;

import com.ssafy.eyesonu.auth.worker.WorkerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobClaimResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisWorkerHeartbeatResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobTargetResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisBatchResultService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisUploadUrlService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobTargetService;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisFailureResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisFailureService;
import jakarta.validation.Valid;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Positive;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/internal/recording-analysis-jobs")
@Tag(name = "녹화 분석 Worker", description = "AI Worker 작업 선점·결과·실패 보고 API")
@SecurityRequirement(name = SwaggerConfig.WORKER_KEY_SCHEME)
public class RecordingAnalysisWorkerController {

    public static final String CLAIM_TOKEN_HEADER = "X-Worker-Claim-Token";

    private final RecordingAnalysisJobClaimService claimService;
    private final RecordingAnalysisBatchResultService resultService;
    private final RecordingAnalysisUploadUrlService uploadUrlService;
    private final RecordingAnalysisJobTargetService targetService;
    private final RecordingAnalysisFailureService failureService;

    public RecordingAnalysisWorkerController(
            RecordingAnalysisJobClaimService claimService,
            RecordingAnalysisBatchResultService resultService,
            RecordingAnalysisUploadUrlService uploadUrlService,
            RecordingAnalysisJobTargetService targetService,
            RecordingAnalysisFailureService failureService) {
        this.claimService = claimService;
        this.resultService = resultService;
        this.uploadUrlService = uploadUrlService;
        this.targetService = targetService;
        this.failureService = failureService;
    }

    @PostMapping("/{jobId}/claim")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobClaimResponse>> claim(
                @AuthenticationPrincipal WorkerPrincipal worker,
                @PathVariable @Positive Long jobId) {
        return ResponseEntity.ok(ApiResponse.of(
                RecordingAnalysisJobClaimResponse.from(
                        claimService.claimForWorker(jobId, worker.workerId()))));
    }

    @GetMapping("/{jobId}/target")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobTargetResponse>> target(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @RequestHeader(CLAIM_TOKEN_HEADER) String claimToken) {
        return ResponseEntity.ok(ApiResponse.of(targetService.find(
                jobId, worker.workerId(), claimToken)));
    }

    @PostMapping("/{jobId}/heartbeat")
    public ResponseEntity<ApiResponse<RecordingAnalysisWorkerHeartbeatResponse>> heartbeat(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @RequestHeader(CLAIM_TOKEN_HEADER) String claimToken) {
        return ResponseEntity.ok(ApiResponse.of(RecordingAnalysisWorkerHeartbeatResponse.running(
                jobId, claimService.renewLease(jobId, worker.workerId(), claimToken))));
    }

    @PostMapping("/{jobId}/upload-urls")
    public ResponseEntity<ApiResponse<RecordingAnalysisUploadUrlCreateResponse>> uploadUrls(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @RequestHeader(CLAIM_TOKEN_HEADER) String claimToken,
            @Valid @RequestBody RecordingAnalysisUploadUrlCreateRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                uploadUrlService.create(jobId, worker.workerId(), claimToken, request)));
    }

    @PostMapping("/{jobId}/result")
    public ResponseEntity<ApiResponse<RecordingAnalysisBatchResultResponse>> result(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @RequestHeader(CLAIM_TOKEN_HEADER) String claimToken,
            @Valid @RequestBody RecordingAnalysisBatchResultRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                resultService.complete(jobId, request, worker.workerId(), claimToken)));
    }

    @PostMapping("/{jobId}/fail")
    public ResponseEntity<ApiResponse<RecordingAnalysisFailureResponse>> fail(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @RequestHeader(CLAIM_TOKEN_HEADER) String claimToken,
            @Valid @RequestBody RecordingAnalysisFailureRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                failureService.fail(jobId, request, worker.workerId(), claimToken)));
    }
}
