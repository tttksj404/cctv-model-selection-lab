package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.Positive;
import java.util.List;

public record CaseCameraRequest(@NotEmpty List<@Positive Long> cameraIds) {
}
