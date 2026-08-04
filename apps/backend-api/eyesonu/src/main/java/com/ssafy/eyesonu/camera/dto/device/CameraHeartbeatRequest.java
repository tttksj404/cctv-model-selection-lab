package com.ssafy.eyesonu.camera.dto.device;

import com.ssafy.eyesonu.recording.dto.MicrosecondOffsetDateTimeDeserializer;
import io.swagger.v3.oas.annotations.media.Schema;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import java.time.OffsetDateTime;
import tools.jackson.databind.annotation.JsonDeserialize;

public record CameraHeartbeatRequest(
        @NotNull
        @Schema(
                description = "RFC 3339 형식의 오프셋 포함 날짜·시간. 소수점 이하 최대 6자리",
                example = "2026-07-20T02:00:00Z")
        @JsonDeserialize(using = MicrosecondOffsetDateTimeDeserializer.class)
        OffsetDateTime occurredAt,
        @NotBlank
        @Schema(description = "장치가 보고한 상태입니다. OFFLINE은 중앙 서버의 timeout 작업으로 판정합니다.",
                allowableValues = {"ONLINE", "ERROR"}, example = "ONLINE")
        String status,
        @Schema(description = "선택 사항인 장치 진단 상세 정보입니다. 데이터베이스에 저장하지 않습니다.", example = "null")
        String detail) {
}
