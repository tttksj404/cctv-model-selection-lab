package com.ssafy.eyesonu.mediaserver.controller.docs;

import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import com.ssafy.eyesonu.mediaserver.dto.MediaServerOptionResponse;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import java.util.List;
import org.springframework.http.ResponseEntity;

@Tag(name = "관리자 미디어 서버", description = "관리자용 미디어 서버 조회 API")
public interface AdminMediaServerControllerDocs {

	@Operation(
			summary = "활성 미디어 서버 옵션 조회",
			description = "카메라 등록 화면에서 선택할 ACTIVE 미디어 서버를 코드 오름차순으로 조회합니다. Device Key 정보는 반환하지 않습니다.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "활성 미디어 서버 옵션 조회 성공", useReturnTypeSchema = true),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "관리자 인증 세션 누락 또는 만료",
					content = @Content(schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "데이터베이스 조회 실패",
					content = @Content(schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<List<MediaServerOptionResponse>>> findActiveOptions();
}
