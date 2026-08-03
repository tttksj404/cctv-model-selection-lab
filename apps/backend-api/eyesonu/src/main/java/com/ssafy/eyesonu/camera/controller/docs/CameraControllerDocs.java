package com.ssafy.eyesonu.camera.controller.docs;

import com.ssafy.eyesonu.camera.dto.CameraCreateRequest;
import com.ssafy.eyesonu.camera.dto.CameraDetailResponse;
import com.ssafy.eyesonu.camera.dto.CameraListResponse;
import com.ssafy.eyesonu.camera.dto.CameraNamePatchRequest;
import com.ssafy.eyesonu.camera.dto.CameraPutRequest;
import com.ssafy.eyesonu.camera.dto.CameraStreamUrlResponse;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.parameters.RequestBody;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.Valid;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.util.List;
import org.springframework.http.ResponseEntity;

@Tag(name = "관리자 카메라", description = "Media Server에 소속된 카메라 관리 API")
public interface CameraControllerDocs {

    @Operation(
            summary = "카메라 목록 조회",
            description = "카메라 목록을 페이지 단위로 조회합니다. 기본 페이지는 0, 크기는 20, 정렬은 createdAt,desc입니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "카메라 목록 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "필터, 페이지, 크기 또는 정렬 조건 오류",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<PagedApiResponse<List<CameraListResponse>>> findAll(
            @Parameter(description = "상태 필터. ONLINE, OFFLINE, ERROR 중 하나", example = "OFFLINE")
            String status,
            @Parameter(description = "카메라 코드 또는 이름 검색어", example = "정문")
            String search,
            @Parameter(description = "0부터 시작하는 페이지 번호", example = "0")
            @Min(0) int page,
            @Parameter(description = "페이지 크기. 1 이상 100 이하", example = "20")
            @Min(1) @Max(100) int size,
            @Parameter(description = "정렬 조건. createdAt, cameraName, cameraCode와 asc/desc 조합", example = "createdAt,desc")
            String sort);

    @Operation(
            summary = "카메라 등록",
            description = "Media Server에 카메라를 등록합니다. 최초 상태는 OFFLINE이며 RTSP URL은 저장하지만 응답에는 포함하지 않습니다.",
            security = {
                @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
                @SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
            })
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "201", description = "카메라 등록 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값 오류",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "CSRF 토큰 누락 또는 불일치",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "Media Server를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "409", description = "이미 존재하는 cameraCode",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "데이터베이스 또는 감사 로그 저장 실패",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CameraDetailResponse>> create(
            @Parameter(hidden = true) AdminPrincipal principal,
            @RequestBody(
                    description = "등록할 카메라 정보. mediaServerId는 존재하는 Media Server ID여야 합니다.",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CameraCreateRequest.class)))
            @Valid CameraCreateRequest request);

    @Operation(
            summary = "카메라 상세 조회",
            description = "카메라의 기본 정보와 소속 Media Server 정보를 조회합니다. RTSP URL은 반환하지 않습니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "카메라 상세 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "카메라를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CameraDetailResponse>> findById(
            @Parameter(description = "조회할 카메라 ID", example = "10") @Positive Long cameraId);

    @Operation(
            summary = "카메라 이름 수정",
            description = "카메라 이름만 수정합니다. cameraCode, 상태, heartbeat 및 나머지 설치 정보는 변경하지 않습니다.",
            security = {
                @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
                @SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
            })
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "카메라 이름 수정 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값 오류",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "CSRF 토큰 누락 또는 불일치",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "카메라를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "데이터베이스 또는 감사 로그 저장 실패",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CameraDetailResponse>> patchName(
            @Parameter(hidden = true) AdminPrincipal principal,
            @Parameter(description = "수정할 카메라 ID", example = "10") @Positive Long cameraId,
            @RequestBody(
                    description = "변경할 카메라 이름",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CameraNamePatchRequest.class)))
            @Valid CameraNamePatchRequest request);

    @Operation(
            summary = "카메라 정보·소속 전체 수정",
            description = "이름, 설치 위치, 좌표, 주소, RTSP URL, Media Server 소속을 전체 수정합니다. cameraCode, 상태, heartbeat는 유지됩니다.",
            security = {
                @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
                @SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
            })
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "카메라 정보·소속 수정 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "요청 값 오류",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "CSRF 토큰 누락 또는 불일치",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "카메라 또는 Media Server를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "데이터베이스 또는 감사 로그 저장 실패",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CameraDetailResponse>> replace(
            @Parameter(hidden = true) AdminPrincipal principal,
            @Parameter(description = "수정할 카메라 ID", example = "10") @Positive Long cameraId,
            @RequestBody(
                    description = "수정할 카메라 정보. cameraCode, 상태, heartbeat는 요청에 포함하지 않습니다.",
                    required = true,
                    content = @Content(schema = @Schema(implementation = CameraPutRequest.class)))
            @Valid CameraPutRequest request);

    @Operation(
            summary = "카메라 스트리밍 URL 조회",
            description = "카메라에 저장된 stream_url을 반환합니다. 관리자 권한이 필요합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "스트리밍 URL 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증 세션이 없거나 만료됨",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "카메라를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<CameraStreamUrlResponse>> findStreamUrlById(
            @Parameter(description = "조회할 카메라 ID", example = "10") @Positive Long cameraId);
}
