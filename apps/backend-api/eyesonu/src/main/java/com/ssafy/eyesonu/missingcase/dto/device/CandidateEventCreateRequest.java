package com.ssafy.eyesonu.missingcase.dto.device;

import com.ssafy.eyesonu.recording.dto.MicrosecondOffsetDateTimeDeserializer;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotEmpty;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;
import jakarta.validation.constraints.PositiveOrZero;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.OffsetDateTime;
import java.util.List;
import tools.jackson.databind.annotation.JsonDeserialize;

public record CandidateEventCreateRequest(
        @NotNull Long caseId,
        @NotBlank @Size(max = 100) String cameraCode,
        @NotBlank @Size(max = 255) String eventId,
        @NotNull @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class) OffsetDateTime detectedAt,
        @NotBlank @Size(max = 500) String frameObjectKey,
        @NotEmpty @Size(max = 100) List<@Valid Detection> detections) {

    public record Detection(
            @NotBlank @Size(max = 100) String trackId,
            @NotNull @DecimalMin("0.0") @DecimalMax("1.0") BigDecimal similarity,
            @NotBlank @Size(max = 500) String cropObjectKey,
            @NotNull @Valid BoundingBox boundingBox) {
    }

    public record BoundingBox(
            @NotNull @PositiveOrZero Integer x,
            @NotNull @PositiveOrZero Integer y,
            @NotNull @Positive Integer width,
            @NotNull @Positive Integer height) {
    }
}
