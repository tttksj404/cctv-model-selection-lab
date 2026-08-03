package com.ssafy.eyesonu.recording.dto.aiworker;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import tools.jackson.databind.JsonNode;

public record AiWorkerCompleteRequest(
        @NotBlank @Size(max = 100) String workerId,
        @NotBlank @Size(max = 200) String leaseToken,
        @NotNull @Valid JsonNode result) {
}
