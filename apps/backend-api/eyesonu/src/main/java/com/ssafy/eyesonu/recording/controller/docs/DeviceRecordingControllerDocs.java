package com.ssafy.eyesonu.recording.controller.docs;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateResponse;
import com.ssafy.eyesonu.recording.dto.device.UploadStatusUpdateRequest;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;

@Tag(name = "디바이스 녹화", description = "디바이스가 녹화 메타데이터와 업로드 상태를 등록하는 API")
public interface DeviceRecordingControllerDocs {

    @Operation(
            summary = "녹화 메타데이터 등록",
            description = "카메라 코드에 해당하는 녹화 메타데이터를 등록합니다.",
            security = @SecurityRequirement(name = "deviceKey"))
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "201", description = "녹화 메타데이터 등록 성공", useReturnTypeSchema = true),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400", description = "요청 값 검증 실패",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "403", description = "디바이스 접근 권한 없음",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "409", description = "중복 녹화 메타데이터",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<RecordingCreateResponse>> create(
            @Parameter(description = "카메라 식별 코드", required = true) String cameraCode,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "녹화 메타데이터 등록 요청", required = true,
                    content = @Content(schema = @Schema(implementation = RecordingCreateRequest.class)))
            RecordingCreateRequest request);

    @Operation(
            summary = "녹화 업로드 상태 변경",
            description = "녹화 파일의 업로드 상태와 파일 크기를 변경합니다.",
            security = @SecurityRequirement(name = "deviceKey"))
    @ApiResponses({
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "200", description = "업로드 상태 변경 성공", useReturnTypeSchema = true),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "400", description = "요청 값 검증 실패",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "403", description = "디바이스 접근 권한 없음",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
            @io.swagger.v3.oas.annotations.responses.ApiResponse(
                    responseCode = "404", description = "녹화 정보 없음",
                    content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
    })
    ResponseEntity<ApiResponse<RecordingCreateResponse>> updateStatus(
            @Parameter(description = "녹화 식별자", required = true) Long recordingId,
            @io.swagger.v3.oas.annotations.parameters.RequestBody(
                    description = "업로드 상태 변경 요청", required = true,
                    content = @Content(schema = @Schema(implementation = UploadStatusUpdateRequest.class)))
            UploadStatusUpdateRequest request);
}
