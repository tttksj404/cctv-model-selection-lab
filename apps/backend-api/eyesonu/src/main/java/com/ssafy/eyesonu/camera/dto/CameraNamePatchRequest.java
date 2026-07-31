package com.ssafy.eyesonu.camera.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CameraNamePatchRequest(
        @NotBlank @Size(max = 100) String cameraName) {
}
