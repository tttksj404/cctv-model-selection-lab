package com.ssafy.eyesonu.missingcase.controller.device;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.controller.docs.DeviceCandidateEventUploadControllerDocs;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateResponse;
import com.ssafy.eyesonu.missingcase.service.CandidateEventUploadUrlService;
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
public class DeviceCandidateEventUploadController implements DeviceCandidateEventUploadControllerDocs {

    private final CandidateEventUploadUrlService uploadUrlService;

    public DeviceCandidateEventUploadController(CandidateEventUploadUrlService uploadUrlService) {
        this.uploadUrlService = uploadUrlService;
    }

    @PostMapping(value = "/candidate-event-upload-urls", consumes = MediaType.APPLICATION_JSON_VALUE)
    @Override
    public ResponseEntity<ApiResponse<CandidateEventUploadUrlCreateResponse>> create(
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @Valid @RequestBody CandidateEventUploadUrlCreateRequest request) {
        return ResponseEntity.status(HttpStatus.CREATED)
                .body(ApiResponse.of(uploadUrlService.create(principal, request)));
    }
}
