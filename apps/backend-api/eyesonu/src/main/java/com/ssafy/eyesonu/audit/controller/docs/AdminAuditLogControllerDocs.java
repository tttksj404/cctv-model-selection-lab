package com.ssafy.eyesonu.audit.controller.docs;

import com.ssafy.eyesonu.audit.dto.admin.AuditLogListResponse;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.PagedApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
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

@Tag(name = "감사 로그", description = "관리자 감사 로그 조회 API")
public interface AdminAuditLogControllerDocs {

    @Operation(
            summary = "감사 로그 목록 조회",
            description = "관리자 감사 로그를 조건별로 조회합니다. from은 포함하고 to는 제외하는 시간 범위로 처리합니다. "
                    + "기본 페이지는 0, 페이지 크기는 20, 정렬은 createdAt,desc입니다.",
            security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
    @ApiResponses({
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "200", description = "감사 로그 목록 조회 성공", useReturnTypeSchema = true),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "400", description = "필터, 페이지, 페이지 크기, 시간 범위 또는 정렬 조건이 올바르지 않음",
                content = @Content(mediaType = "application/json",
                        schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "401", description = "관리자 인증이 필요함",
                content = @Content(mediaType = "application/json",
                        schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "403", description = "관리자 권한이 없음",
                content = @Content(mediaType = "application/json",
                        schema = @Schema(implementation = ApiErrorResponse.class))),
        @io.swagger.v3.oas.annotations.responses.ApiResponse(
                responseCode = "503", description = "감사 로그 조회 중 데이터베이스 오류가 발생함",
                content = @Content(mediaType = "application/json",
                        schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<PagedApiResponse<List<AuditLogListResponse>>> findAll(
            @Parameter(description = "조회할 사건 ID", example = "20") @Positive Long caseId,
            @Parameter(description = "작업 유형의 정확한 값", example = "CASE_STATUS_CHANGED") String actionType,
            @Parameter(description = "관리자 이름, 로그인 ID 또는 관리자 ID 검색어", example = "관리자") String actor,
            @Parameter(
                    description = "조회 시작 시각. RFC 3339 형식이며 범위에 포함됩니다.",
                    example = "2026-08-02T10:00:00+09:00")
                    OffsetDateTime from,
            @Parameter(
                    description = "조회 종료 시각. RFC 3339 형식이며 범위에서 제외됩니다.",
                    example = "2026-08-02T11:00:00+09:00")
                    OffsetDateTime to,
            @Parameter(description = "0부터 시작하는 페이지 번호", example = "0") @Min(0) int page,
            @Parameter(description = "페이지 크기. 1 이상 100 이하이며 기본값은 20입니다.", example = "20")
                    @Min(1) @Max(100) int size,
            @Parameter(
                    description = "정렬 조건. 허용 필드와 방향만 사용할 수 있습니다.",
                    example = "createdAt,desc",
                    schema = @Schema(allowableValues = {
                            "createdAt,asc", "createdAt,desc",
                            "id,asc", "id,desc",
                            "actionType,asc", "actionType,desc",
                            "adminId,asc", "adminId,desc",
                            "caseId,asc", "caseId,desc"
                    }))
                    String sort);
}
