package com.ssafy.eyesonu.recording.controller.internal;

import com.ssafy.eyesonu.auth.worker.WorkerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobClaimResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisUploadUrlCreateResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisBatchResultService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisUploadUrlService;
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
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/internal/recording-analysis-jobs")
@Tag(name = "녹화 분석 Worker", description = "AI Worker 작업 선점·결과·실패 보고 API")
@SecurityRequirement(name = SwaggerConfig.WORKER_KEY_SCHEME)
public class RecordingAnalysisWorkerController {

    private final RecordingAnalysisJobClaimService claimService;
    private final RecordingAnalysisBatchResultService resultService;
    private final RecordingAnalysisUploadUrlService uploadUrlService;
    private final RecordingAnalysisFailureService failureService;

    public RecordingAnalysisWorkerController(
            RecordingAnalysisJobClaimService claimService,
            RecordingAnalysisBatchResultService resultService,
            RecordingAnalysisUploadUrlService uploadUrlService,
            RecordingAnalysisFailureService failureService) {
        this.claimService = claimService;
        this.resultService = resultService;
        this.uploadUrlService = uploadUrlService;
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

    @PostMapping("/{jobId}/upload-urls")
    public ResponseEntity<ApiResponse<RecordingAnalysisUploadUrlCreateResponse>> uploadUrls(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody RecordingAnalysisUploadUrlCreateRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                uploadUrlService.create(jobId, worker.workerId(), request)));
    }

    @PostMapping("/{jobId}/result")
    public ResponseEntity<ApiResponse<RecordingAnalysisBatchResultResponse>> result(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody RecordingAnalysisBatchResultRequest request) {
        return ResponseEntity.ok(ApiResponse.of(resultService.complete(jobId, request, worker.workerId())));
    }

    @PostMapping("/{jobId}/fail")
    public ResponseEntity<ApiResponse<RecordingAnalysisFailureResponse>> fail(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody RecordingAnalysisFailureRequest request) {
        return ResponseEntity.ok(ApiResponse.of(failureService.fail(jobId, request, worker.workerId())));
    }
}
