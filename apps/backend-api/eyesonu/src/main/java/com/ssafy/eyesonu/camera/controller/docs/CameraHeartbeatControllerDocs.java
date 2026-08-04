package com.ssafy.eyesonu.camera.controller.docs;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.camera.dto.device.CameraHeartbeatRequest;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "디바이스 카메라", description = "미디어 서버 카메라 Heartbeat 수신 API")
public interface CameraHeartbeatControllerDocs {

    @Operation(
            summary = "카메라 Heartbeat 수신",
            description = "인증된 미디어 서버에 소속된 카메라의 상태와 마지막 Heartbeat 시간을 갱신합니다. "
                    + "중앙 서버의 timeout 작업이 OFFLINE 상태를 판정합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "204", description = "Heartbeat 수신 성공"),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값 또는 날짜·시간 형식이 올바르지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "디바이스 인증이 필요하거나 인증 정보가 올바르지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "카메라가 다른 미디어 서버에 소속됨",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "카메라를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "데이터베이스를 사용할 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<Void> receive(
            @Parameter(description = "카메라 코드", required = true) String cameraCode,
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "카메라 Heartbeat 상태 및 발생 시각",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CameraHeartbeatRequest.class)))
            CameraHeartbeatRequest request);
}
