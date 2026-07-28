package com.ssafy.eyesonu.recording.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.recording.controller.docs.AdminRecordingControllerDocs;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingSearchCondition;
import com.ssafy.eyesonu.recording.service.AdminRecordingPageResult;
import com.ssafy.eyesonu.recording.service.RecordingQueryService;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.format.annotation.DateTimeFormat;
import org.springframework.http.ResponseEntity;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/recordings")
public class AdminRecordingController implements AdminRecordingControllerDocs {

    private final RecordingQueryService queryService;

    public AdminRecordingController(RecordingQueryService queryService) {
        this.queryService = queryService;
    }

    @GetMapping
    public ResponseEntity<PagedApiResponse<List<AdminRecordingListResponse>>> findAll(
            @RequestParam(required = false) @Positive Long cameraId,
            @RequestParam(required = false)
                    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime startFrom,
            @RequestParam(required = false)
                    @DateTimeFormat(iso = DateTimeFormat.ISO.DATE_TIME) OffsetDateTime startTo,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
            @RequestParam(defaultValue = "startTime,desc") String sort) {
        AdminRecordingPageResult result = queryService.findAll(
                new AdminRecordingSearchCondition(cameraId, startFrom, startTo, page, size, sort));
        PageMeta meta = new PageMeta(
                result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort());
        return ResponseEntity.ok(PagedApiResponse.of(result.recordings(), meta));
    }

    @GetMapping("/{recordingId}")
    public ResponseEntity<ApiResponse<AdminRecordingDetailResponse>> findById(
            @PathVariable @Positive Long recordingId) {
        return ResponseEntity.ok(ApiResponse.of(queryService.findById(recordingId)));
    }
}
