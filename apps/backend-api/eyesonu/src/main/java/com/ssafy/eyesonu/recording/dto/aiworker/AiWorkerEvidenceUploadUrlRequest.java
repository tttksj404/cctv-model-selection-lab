package com.ssafy.eyesonu.recording.dto.aiworker;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.List;

public record AiWorkerEvidenceUploadUrlRequest(
        @NotBlank @Size(max = 100) String workerId,
        @NotBlank @Size(max = 200) String leaseToken,
        @NotNull @Size(max = AiWorkerProtocol.MAX_CANDIDATES)
        List<@Valid Candidate> candidates) {

    public record Candidate(
            @NotBlank @Pattern(regexp = "^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$") String candidateKey,
            @NotBlank @Pattern(regexp = "^image/(jpeg|png)$") String frameContentType,
            @NotBlank @Pattern(regexp = "^image/(jpeg|png)$") String cropContentType) {
    }
}
