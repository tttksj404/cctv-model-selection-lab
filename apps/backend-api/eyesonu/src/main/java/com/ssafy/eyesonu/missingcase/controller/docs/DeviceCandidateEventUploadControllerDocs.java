package com.ssafy.eyesonu.missingcase.controller.docs;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.device.CandidateEventUploadUrlCreateResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "디바이스 후보 이벤트", description = "후보 이미지 업로드 URL 발급 및 탐지 메타데이터 등록 API")
public interface DeviceCandidateEventUploadControllerDocs {

    @Operation(
            summary = "후보 이미지 업로드 URL 생성",
            description = "한 개의 프레임과 해당 프레임의 crop 이미지에 대해 짧은 유효기간의 MinIO/S3 PUT URL과 서버가 관리하는 객체 키를 생성합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.DEVICE_KEY_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "업로드 URL 생성 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "Content-Type이 올바르지 않거나 중복된 트랙 ID",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "디바이스 인증이 필요하거나 인증 정보가 올바르지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "카메라가 다른 미디어 서버에 소속됨",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "사건 또는 카메라를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "422", description = "사건을 검색할 수 없거나 카메라가 선택되지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "스토리지를 사용할 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CandidateEventUploadUrlCreateResponse>> create(
            @Parameter(hidden = true) MediaServerPrincipal principal,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "후보 프레임 및 crop 이미지 업로드 요청",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CandidateEventUploadUrlCreateRequest.class)))
                    CandidateEventUploadUrlCreateRequest request);
}
