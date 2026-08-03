package com.ssafy.eyesonu.recording.dto.aiworker;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AiWorkerHeartbeatRequest(
        @NotBlank @Size(max = 100) String workerId,
        @NotBlank @Size(max = 200) String leaseToken) {
}
