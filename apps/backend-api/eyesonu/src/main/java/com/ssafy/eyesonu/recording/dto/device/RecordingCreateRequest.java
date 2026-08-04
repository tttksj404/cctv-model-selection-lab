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
                description = "RFC 3339 형식의 오프셋 필수 날짜·시간. 소수점 이하 최대 6자리",
                example = "2026-07-20T01:50:00.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime startTime,
        @NotNull
        @Schema(
                description = "startTime 이후의 RFC 3339 형식 오프셋 필수 날짜·시간. 소수점 이하 최대 6자리",
                example = "2026-07-20T02:00:00.123456Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime endTime,
        @NotBlank
        @Size(max = 500)
        @Schema(
                description = "대소문자를 구분하는 recordings/{cameraCode}/.../*.mp4 형식의 스토리지 객체 키",
                minLength = 1,
                maxLength = 500,
                example = "recordings/camera-01/2026/07/20/015000.mp4")
        String objectKey) {
}
