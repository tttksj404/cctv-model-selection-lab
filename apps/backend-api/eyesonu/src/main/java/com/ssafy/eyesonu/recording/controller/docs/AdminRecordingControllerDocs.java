package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.admin.AdminRecordingResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.time.LocalDateTime;
import java.util.List;
import org.springframework.http.ResponseEntity;

@Tag(name = "관리자 녹화", description = "관리자가 녹화 메타데이터를 조회하는 API")
public interface AdminRecordingControllerDocs {

    @Operation(
            summary = "녹화 목록 조회",
            description = "카메라, 업로드 상태, 촬영 시간 조건으로 녹화 목록을 조회합니다.",
            security = @SecurityRequirement(name = "sessionCookie"))
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "녹화 목록 조회 성공", useReturnTypeSchema = true),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400", description = "조회 조건 검증 실패",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<List<AdminRecordingResponse>>> findAll(
            @Parameter(description = "카메라 식별자") Long cameraId,
            @Parameter(description = "업로드 상태") com.ssafy.eyesonu.recording.domain.UploadStatus uploadStatus,
            @Parameter(description = "촬영 시작 시간 조건") LocalDateTime startFrom,
            @Parameter(description = "촬영 종료 시간 조건") LocalDateTime startTo);

    @Operation(
            summary = "녹화 상세 조회",
            description = "녹화 식별자로 녹화 메타데이터를 조회합니다.",
            security = @SecurityRequirement(name = "sessionCookie"))
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "녹화 상세 조회 성공", useReturnTypeSchema = true),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404", description = "녹화 정보 없음",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<AdminRecordingResponse>> findById(
            @Parameter(description = "녹화 식별자", required = true) Long recordingId);
}
