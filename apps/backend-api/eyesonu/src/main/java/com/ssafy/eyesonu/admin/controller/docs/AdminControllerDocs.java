package com.ssafy.eyesonu.admin.controller.docs;

import com.ssafy.eyesonu.admin.dto.AdminResponse;
import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.dto.AdminUpdateResponse;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;

@Tag(name = "관리자", description = "로그인한 관리자 정보 API")
public interface AdminControllerDocs {

	@Operation(
			summary = "내 정보 조회",
			description = "현재 로그인한 관리자의 정보를 조회합니다.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 정보 조회 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 세션 누락 또는 만료",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminResponse>> me(
			@Parameter(hidden = true) AdminPrincipal principal);

	@Operation(
			summary = "내 정보 수정",
			description = "관리자 이름 또는 비밀번호를 수정합니다. 비밀번호가 변경되면 "
					+ "현재 세션이 종료되므로 다시 로그인해야 합니다.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 정보 수정 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "요청 값 또는 현재 비밀번호 검증 실패",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 세션 누락 또는 만료",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "CSRF 토큰 누락 또는 불일치",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "관리자 정보 수정 또는 데이터베이스 일시 장애",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminUpdateResponse>> update(
			@Parameter(hidden = true) AdminPrincipal principal,
			@Parameter(hidden = true) Authentication authentication,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "변경할 관리자 정보",
					required = true,
					content = @Content(schema = @Schema(implementation = AdminUpdateRequest.class)))
			AdminUpdateRequest body,
			@Parameter(hidden = true) HttpServletRequest request,
			@Parameter(hidden = true) HttpServletResponse response);
}
