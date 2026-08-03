package com.ssafy.eyesonu.recording.dto.aiworker;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record AiWorkerFailRequest(
        @NotBlank @Size(max = 100) String workerId,
        @NotBlank @Size(max = 200) String leaseToken,
        @NotBlank @Size(max = 100) String errorCode,
        @NotBlank @Size(max = 2_000) String errorMessage,
        @NotNull Boolean retryable) {
}
