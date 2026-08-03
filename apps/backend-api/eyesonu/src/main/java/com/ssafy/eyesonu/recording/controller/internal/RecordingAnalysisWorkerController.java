package com.ssafy.eyesonu.recording.controller.internal;

import com.ssafy.eyesonu.auth.worker.WorkerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisJobClaimResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingAnalysisBatchResultResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobClaimService;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisBatchResultService;
import jakarta.validation.Valid;
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
public class RecordingAnalysisWorkerController {

    private final RecordingAnalysisJobClaimService claimService;
    private final RecordingAnalysisBatchResultService resultService;

    public RecordingAnalysisWorkerController(
            RecordingAnalysisJobClaimService claimService,
            RecordingAnalysisBatchResultService resultService) {
        this.claimService = claimService;
        this.resultService = resultService;
    }

    @PostMapping("/{jobId}/claim")
    public ResponseEntity<ApiResponse<RecordingAnalysisJobClaimResponse>> claim(
                @AuthenticationPrincipal WorkerPrincipal worker,
                @PathVariable @Positive Long jobId) {
        return ResponseEntity.ok(ApiResponse.of(
                RecordingAnalysisJobClaimResponse.from(
                        claimService.claimForWorker(jobId, worker.workerId()))));
    }

    @PostMapping("/{jobId}/result")
    public ResponseEntity<ApiResponse<RecordingAnalysisBatchResultResponse>> result(
            @AuthenticationPrincipal WorkerPrincipal worker,
            @PathVariable @Positive Long jobId,
            @Valid @RequestBody RecordingAnalysisBatchResultRequest request) {
        return ResponseEntity.ok(ApiResponse.of(resultService.complete(jobId, request, worker.workerId())));
    }
}
