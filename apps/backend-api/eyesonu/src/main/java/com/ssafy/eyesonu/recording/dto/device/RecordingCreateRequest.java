package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.dto.MicrosecondOffsetDateTimeDeserializer;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.time.OffsetDateTime;
import tools.jackson.databind.annotation.JsonDeserialize;

public record RecordingCreateRequest(
        @NotNull
        @Schema(
                description = "RFC 3339 date-time with a required offset and at most 6 fractional digits",
                example = "2026-07-20T01:50:00.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime startTime,
        @NotNull
        @Schema(
                description = "RFC 3339 date-time after startTime, with a required offset and at most 6 fractional digits",
                example = "2026-07-20T02:00:00.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime endTime,
        @NotBlank
        @Size(max = 500)
        @Schema(
                description = "Case-sensitive recordings/{cameraCode}/.../*.mp4 storage key",
                minLength = 1,
                maxLength = 500,
                example = "recordings/camera-01/2026/07/20/015000.mp4")
        String objectKey) {
}
