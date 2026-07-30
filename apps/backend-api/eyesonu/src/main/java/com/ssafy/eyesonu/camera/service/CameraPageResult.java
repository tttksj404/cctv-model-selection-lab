package com.ssafy.eyesonu.camera.service;

import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import java.util.List;

public record CameraPageResult(
        List<CameraListResponse> cameras,
        int page,
        int size,
        long totalElements,
        int totalPages,
        String sort) {
}
