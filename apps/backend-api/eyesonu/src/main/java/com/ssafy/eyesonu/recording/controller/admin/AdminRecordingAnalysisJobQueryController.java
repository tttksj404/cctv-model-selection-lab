package com.ssafy.eyesonu.recording.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.admin.RecordingAnalysisJobResponse;
import com.ssafy.eyesonu.recording.service.RecordingAnalysisJobService;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/recording-analysis-jobs")
public class AdminRecordingAnalysisJobQueryController {

    private final RecordingAnalysisJobService service;

    public AdminRecordingAnalysisJobQueryController(RecordingAnalysisJobService service) {
        this.service = service;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<RecordingAnalysisJobResponse>>> findAll(
            @RequestParam @Size(min = 1, max = 100) List<@Positive Long> caseIds) {
        return ResponseEntity.ok(ApiResponse.of(service.findAllByCaseIds(caseIds)));
    }
}
