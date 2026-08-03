package com.ssafy.eyesonu.missingcase.dto.device;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;
import java.util.List;

public record CandidateEventUploadUrlCreateRequest(
        @NotNull Long caseId,
        @NotBlank @Size(max = 100) String cameraCode,
        @NotBlank @Size(max = 255) String eventId,
        @NotNull @Valid Image frame,
        @NotEmpty @Size(max = 100) List<@Valid Detection> detections) {

    public record Image(
            @NotBlank
            @Pattern(regexp = "image/(jpeg|png)", message = "contentType must be image/jpeg or image/png")
            String contentType) {
    }

    public record Detection(
            @NotBlank @Size(max = 100) String trackId,
            @NotBlank
            @Pattern(regexp = "image/(jpeg|png)", message = "contentType must be image/jpeg or image/png")
            String contentType) {
    }
}
