package com.ssafy.eyesonu.recording.dto.device;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.List;

public record RecordingAnalysisUploadUrlCreateRequest(
        @NotNull @NotEmpty @Size(max = 1000) List<@Valid Candidate> candidates) {

    public record Candidate(
            @NotBlank @Size(max = 100) String trackId,
            @NotBlank
            @Pattern(regexp = "image/(jpeg|png)", message = "frameContentType must be image/jpeg or image/png")
            String frameContentType,
            @NotBlank
            @Pattern(regexp = "image/(jpeg|png)", message = "cropContentType must be image/jpeg or image/png")
            String cropContentType) {
    }
}
