package com.ssafy.eyesonu.recording.dto.device;

import com.ssafy.eyesonu.recording.dto.MicrosecondOffsetDateTimeDeserializer;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotNull;
import java.time.OffsetDateTime;
import tools.jackson.databind.annotation.JsonDeserialize;

public record RecordingUploadUrlCreateRequest(
        @NotNull
        @Schema(
                description = "RFC 3339 형식의 오프셋 필수 녹화 시작 시각. 소수점 이하 최대 6자리",
                example = "2026-08-04T03:15:30.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime startTime,
        @NotNull
        @Schema(
                description = "startTime 이후의 RFC 3339 형식 오프셋 필수 녹화 종료 시각. 소수점 이하 최대 6자리",
                example = "2026-08-04T03:16:00.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime endTime) {
}
