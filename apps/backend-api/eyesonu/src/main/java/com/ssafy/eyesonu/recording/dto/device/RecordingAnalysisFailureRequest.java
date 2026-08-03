package com.ssafy.eyesonu.recording.dto.device;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record RecordingAnalysisFailureRequest(
        @NotBlank @Size(max = 255) String resultId,
        @NotBlank @Size(max = 100) String errorCode,
        @Size(max = 1000) String errorMessage) {
}
