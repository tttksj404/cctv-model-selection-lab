package com.ssafy.eyesonu.camera.controller.device;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.controller.docs.CameraHeartbeatControllerDocs;
import com.ssafy.eyesonu.camera.dto.device.CameraHeartbeatRequest;
import com.ssafy.eyesonu.camera.service.CameraHeartbeatService;
import jakarta.validation.Valid;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/device/cameras")
public class CameraHeartbeatController implements CameraHeartbeatControllerDocs {

    private final CameraHeartbeatService heartbeatService;

    public CameraHeartbeatController(CameraHeartbeatService heartbeatService) {
        this.heartbeatService = heartbeatService;
    }

    @PostMapping(value = "/{cameraCode}/heartbeat", consumes = MediaType.APPLICATION_JSON_VALUE)
    @Override
    public ResponseEntity<Void> receive(
            @PathVariable String cameraCode,
            @AuthenticationPrincipal MediaServerPrincipal principal,
            @Valid @RequestBody CameraHeartbeatRequest request) {
        heartbeatService.receive(principal, cameraCode, request);
        return ResponseEntity.noContent().build();
    }
}
