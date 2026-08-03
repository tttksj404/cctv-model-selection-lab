package com.ssafy.eyesonu.camera.controller.admin;

import com.ssafy.eyesonu.camera.controller.docs.CameraControllerDocs;
import com.ssafy.eyesonu.camera.dto.CameraCreateRequest;
import com.ssafy.eyesonu.camera.dto.CameraDetailResponse;
import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import com.ssafy.eyesonu.camera.dto.CameraNamePatchRequest;
import com.ssafy.eyesonu.camera.dto.CameraPutRequest;
import com.ssafy.eyesonu.camera.dto.CameraStreamUrlResponse;
import com.ssafy.eyesonu.camera.service.CameraPageResult;
import com.ssafy.eyesonu.camera.service.CameraService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PageMeta;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.util.List;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.validation.annotation.Validated;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@Validated
@RestController
@RequestMapping("/api/v1/admin/cameras")
public class CameraController implements CameraControllerDocs {

    private final CameraService cameraService;

    public CameraController(CameraService cameraService) {
        this.cameraService = cameraService;
    }

    @GetMapping
    @Override
    public ResponseEntity<PagedApiResponse<List<CameraListResponse>>> findAll(
            @RequestParam(required = false) String status,
            @RequestParam(required = false) String search,
            @RequestParam(defaultValue = "0") @Min(0) int page,
            @RequestParam(defaultValue = "20") @Min(1) @Max(100) int size,
            @RequestParam(defaultValue = "createdAt,desc") String sort) {
        CameraPageResult result = cameraService.findAdminPage(status, search, page, size, sort);
        PageMeta meta = new PageMeta(
                result.page(), result.size(), result.totalElements(), result.totalPages(), result.sort());
        return ResponseEntity.ok(PagedApiResponse.of(result.cameras(), meta));
    }

    @PostMapping
    @Override
    public ResponseEntity<ApiResponse<CameraDetailResponse>> create(
            @AuthenticationPrincipal AdminPrincipal principal,
            @Valid @RequestBody CameraCreateRequest request) {
        CameraDetailResponse response = cameraService.create(principal.getAdminId(), request);
        return ResponseEntity.status(HttpStatus.CREATED).body(ApiResponse.of(response));
    }

    @GetMapping("/{cameraId}")
    @Override
    public ResponseEntity<ApiResponse<CameraDetailResponse>> findById(
            @PathVariable @Positive Long cameraId) {
        return ResponseEntity.ok(ApiResponse.of(cameraService.findAdminById(cameraId)));
    }

    @GetMapping("/{cameraId}/streamUrl")
    @Override
    public ResponseEntity<ApiResponse<CameraStreamUrlResponse>> findStreamUrlById(
            @PathVariable @Positive Long cameraId) {
        return ResponseEntity.ok(ApiResponse.of(cameraService.findStreamUrlById(cameraId)));
    }

    @PatchMapping("/{cameraId}/name")
    @Override
    public ResponseEntity<ApiResponse<CameraDetailResponse>> patchName(
            @AuthenticationPrincipal AdminPrincipal principal,
            @PathVariable @Positive Long cameraId,
            @Valid @RequestBody CameraNamePatchRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                cameraService.patchName(principal.getAdminId(), cameraId, request)));
    }

    @PutMapping("/{cameraId}")
    @Override
    public ResponseEntity<ApiResponse<CameraDetailResponse>> replace(
            @AuthenticationPrincipal AdminPrincipal principal,
            @PathVariable @Positive Long cameraId,
            @Valid @RequestBody CameraPutRequest request) {
        return ResponseEntity.ok(ApiResponse.of(
                cameraService.replace(principal.getAdminId(), cameraId, request)));
    }
}
