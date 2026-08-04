package com.ssafy.eyesonu.recording.controller.device;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.controller.docs.DeviceRecordingControllerDocs;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateResponse;
import com.ssafy.eyesonu.recording.service.RecordingCommandService;
import com.ssafy.eyesonu.recording.service.RecordingCreateResult;
import com.ssafy.eyesonu.recording.service.RecordingUploadUrlService;
import jakarta.validation.Valid;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.security.core.annotation.AuthenticationPrincipal;

@RestController
@RequestMapping("/api/v1/device")
public class DeviceRecordingController implements DeviceRecordingControllerDocs {

    private final RecordingCommandService commandService;
    private final RecordingUploadUrlService uploadUrlService;

    public DeviceRecordingController(
            RecordingCommandService commandService,
            RecordingUploadUrlService uploadUrlService) {
        this.commandService = commandService;
        this.uploadUrlService = uploadUrlService;
    }

    @PostMapping(value = "/cameras/{cameraCode}/recording-upload-urls", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ApiResponse<RecordingUploadUrlCreateResponse>> createUploadUrl(
            @PathVariable String cameraCode,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @Valid @RequestBody RecordingUploadUrlCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.of(
                uploadUrlService.create(principal, cameraCode, idempotencyKey, request)));
    }

    @PostMapping(value = "/cameras/{cameraCode}/recordings", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<ApiResponse<RecordingCreateResponse>> create(
            @PathVariable String cameraCode,
            @RequestHeader("Idempotency-Key") String idempotencyKey,
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @Valid @RequestBody RecordingCreateRequest request) {
        RecordingCreateResult result = commandService.create(principal, cameraCode, idempotencyKey, request);
        HttpStatus status = result.duplicate() ? HttpStatus.OK : HttpStatus.CREATED;
        return ResponseEntity.status(status).body(ApiResponse.of(
                RecordingCreateResponse.from(result.recording(), result.duplicate())));
    }
}
