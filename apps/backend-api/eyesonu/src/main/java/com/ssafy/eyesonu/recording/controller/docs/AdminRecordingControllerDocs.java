package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingDetailResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingListResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.Positive;
import java.time.OffsetDateTime;
import java.util.List;
import org.springframework.http.ResponseEntity;

@Tag(name = "관리자 녹화", description = "녹화 메타데이터 조회 및 재생 URL 발급 API")
public interface AdminRecordingControllerDocs {

    @Operation(
            summary = "녹화 목록 조회",
            description = "일관된 정렬 기준으로 데이터베이스 페이지네이션 목록을 반환합니다. 시간 필터는 구간 겹침을 기준으로 적용합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "녹화 목록 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "필터, 페이지, 크기 또는 정렬 조건이 올바르지 않음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<PagedApiResponse<List<AdminRecordingListResponse>>> findAll(
            @Parameter(description = "카메라 ID") @Positive Long cameraId,
            @Parameter(description = "구간 시작 시각. RFC 3339 오프셋 형식이며 소수점 이하 최대 6자리")
                    OffsetDateTime startFrom,
            @Parameter(description = "구간 종료 시각. RFC 3339 오프셋 형식이며 소수점 이하 최대 6자리")
                    OffsetDateTime startTo,
            @Parameter(description = "0부터 시작하는 페이지 번호", example = "0") @Min(0) int page,
            @Parameter(description = "페이지 크기. 1 이상 100 이하", example = "20") @Min(1) @Max(100) int size,
            @Parameter(
                    description = "허용된 필드·방향 조합",
                    example = "startTime,desc",
                    schema = @Schema(allowableValues = {
                            "startTime,asc", "startTime,desc", "createdAt,asc", "createdAt,desc"
                    }))
                    String sort);

    @Operation(
            summary = "녹화 상세 조회",
            description = "녹화 메타데이터와 짧은 유효기간의 재생 URL을 반환합니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "녹화 상세 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "404", description = "녹화를 찾을 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "재생 URL을 발급할 수 없음",
                content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<AdminRecordingDetailResponse>> findById(
            @Parameter(description = "녹화 ID", required = true) @Positive Long recordingId);
}
