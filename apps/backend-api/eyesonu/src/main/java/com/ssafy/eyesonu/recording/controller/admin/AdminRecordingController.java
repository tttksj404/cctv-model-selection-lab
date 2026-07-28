package com.ssafy.eyesonu.recording.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.domain.UploadStatus;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import com.ssafy.eyesonu.recording.service.RecordingQueryService;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;
import com.ssafy.eyesonu.recording.controller.docs.AdminRecordingControllerDocs;

@RestController
@RequestMapping("/api/v1/admin/recordings")
public class AdminRecordingController implements AdminRecordingControllerDocs {
    private final RecordingQueryService queryService;

    public AdminRecordingController(RecordingQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<AdminRecordingResponse>>> findAll(
            @RequestParam(required = false) Long cameraId,
            @RequestParam(required = false) UploadStatus uploadStatus,
            @RequestParam(required = false) LocalDateTime startFrom,
            @RequestParam(required = false) LocalDateTime startTo) {
        List<AdminRecordingResponse> response = queryService.findAll(
                new AdminRecordingSearchCondition(cameraId, uploadStatus, startFrom, startTo))
                .stream().map(AdminRecordingResponse::from).toList();
        return ResponseEntity.ok(ApiResponse.of(response));
    }

    @GetMapping("/{recordingId}")
    public ResponseEntity<ApiResponse<AdminRecordingResponse>> findById(@PathVariable Long recordingId) {
        return ResponseEntity.ok(ApiResponse.of(
                AdminRecordingResponse.from(queryService.findById(recordingId))));
    }
}
