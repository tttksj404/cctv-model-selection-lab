package com.ssafy.eyesonu.camera.dto;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;

public record CameraCreateRequest(
        @NotNull @Positive Long mediaServerId,
        @NotBlank
        @Size(max = 100)
        @Pattern(
                regexp = "[A-Za-z0-9._-]+",
                message = "영문, 숫자, 마침표, 밑줄, 하이픈만 사용할 수 있습니다.")
        String cameraCode,
        @NotBlank @Size(max = 100) String cameraName,
        @NotNull @DecimalMin("-90.0") @DecimalMax("90.0") BigDecimal latitude,
        @NotNull @DecimalMin("-180.0") @DecimalMax("180.0") BigDecimal longitude,
        @NotBlank @Size(max = 255) String address,
        @NotBlank @Size(max = 500) String rtspUrl) {
}
