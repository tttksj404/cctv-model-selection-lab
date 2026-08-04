package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingUploadUrlCreateResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.enums.ParameterIn;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "디바이스 녹화", description = "미디어 서버 녹화 업로드 URL 발급 및 메타데이터 등록 API")
public interface DeviceRecordingControllerDocs {

    @Operation(
            summary = "녹화 업로드 URL 발급",
            description = "녹화 한 건의 서버 소유 object key와 짧은 유효 기간의 PUT URL을 발급합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "업로드 URL 발급 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값, 시각 또는 멱등성 키가 올바르지 않음",
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
                responseCode = "409", description = "해당 멱등성 키로 녹화가 이미 등록됨",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "415", description = "Content-Type이 application/json이 아님",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "스토리지를 사용할 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<RecordingUploadUrlCreateResponse>> createUploadUrl(
            @Parameter(description = "카메라 코드", required = true, example = "camera-01") String cameraCode,
            @Parameter(
                    name = "Idempotency-Key",
                    description = "URL 재발급과 녹화 완료 등록에 재사용하는 정규 UUID",
                    in = ParameterIn.HEADER,
                    required = true,
                    schema = @Schema(type = "string", format = "uuid",
                            example = "550e8400-e29b-41d4-a716-446655440000"))
                    String idempotencyKey,
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "서버 소유 object key 생성에 사용하는 녹화 시간 범위",
                    required = true,
                    content = @Content(schema = @Schema(implementation = RecordingUploadUrlCreateRequest.class)))
                    RecordingUploadUrlCreateRequest request);

    @Operation(
            summary = "업로드된 녹화 메타데이터 등록",
            description = "업로드된 객체를 검증하고 메타데이터를 원자적으로 등록합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "녹화 등록 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "멱등성 재요청 처리 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값, 시각, 객체 키 또는 멱등성 키가 올바르지 않음",
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
                responseCode = "409", description = "멱등성 키 충돌 또는 중복 객체",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "413", description = "스토리지 객체가 설정된 크기 제한을 초과함",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "415", description = "Content-Type이 application/json이 아님",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "422", description = "스토리지 객체가 없거나 올바르지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "스토리지를 사용할 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<RecordingCreateResponse>> create(
            @Parameter(description = "카메라 코드", required = true, example = "camera-01") String cameraCode,
            @Parameter(
                    name = "Idempotency-Key",
                    description = "인증된 미디어 서버 범위에서 사용하는 정규 UUID",
                    in = ParameterIn.HEADER,
                    required = true,
                    schema = @Schema(type = "string", format = "uuid",
                            example = "550e8400-e29b-41d4-a716-446655440000"))
                    String idempotencyKey,
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "업로드된 녹화 메타데이터",
                    required = true,
                    content = @Content(schema = @Schema(implementation = RecordingCreateRequest.class)))
                    RecordingCreateRequest request);
}
