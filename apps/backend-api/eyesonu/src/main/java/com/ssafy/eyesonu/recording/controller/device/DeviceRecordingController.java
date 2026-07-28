package com.ssafy.eyesonu.recording.controller.device;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateResponse;
import com.ssafy.eyesonu.recording.dto.device.UploadStatusUpdateRequest;
import com.ssafy.eyesonu.recording.service.RecordingCommandService;
import jakarta.validation.Valid;
import com.ssafy.eyesonu.recording.controller.docs.DeviceRecordingControllerDocs;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/device")
public class    DeviceRecordingController implements DeviceRecordingControllerDocs {
    private final RecordingCommandService commandService;

    public DeviceRecordingController(RecordingCommandService commandService) {
        this.commandService = commandService;
    }

    @PostMapping("/cameras/{cameraCode}/recordings")
    public ResponseEntity<ApiResponse<RecordingCreateResponse>> create(
            @PathVariable String cameraCode, @Valid @RequestBody RecordingCreateRequest request) {
        return ResponseEntity.status(201).body(ApiResponse.of(
                RecordingCreateResponse.from(commandService.create(cameraCode, request))));
    }

    @PatchMapping("/{recordingId}/upload-status")
    public ResponseEntity<ApiResponse<RecordingCreateResponse>> updateStatus(
            @PathVariable Long recordingId, @Valid @RequestBody UploadStatusUpdateRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                RecordingCreateResponse.from(commandService.updateStatus(recordingId, request))));
    }
}
