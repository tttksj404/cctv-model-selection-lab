package com.ssafy.eyesonu.auth.controller.docs;

import com.ssafy.eyesonu.admin.dto.AdminResponse;
import com.ssafy.eyesonu.auth.dto.AdminLoginRequest;
import com.ssafy.eyesonu.common.api.ApiErrorResponse;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.common.config.SwaggerConfig;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.headers.Header;
import io.swagger.v3.oas.annotations.media.Content;
import io.swagger.v3.oas.annotations.media.Schema;
import io.swagger.v3.oas.annotations.responses.ApiResponses;
import io.swagger.v3.oas.annotations.security.SecurityRequirement;
import io.swagger.v3.oas.annotations.tags.Tag;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.springframework.http.ResponseEntity;
import org.springframework.security.web.csrf.CsrfToken;

@Tag(name = "인증", description = "관리자 세션 인증과 CSRF 토큰 API")
public interface AuthControllerDocs {

	@Operation(
			summary = "CSRF 토큰 발급",
			description = "XSRF-TOKEN 쿠키를 발급합니다. Swagger에서는 쿠키 값을 "
					+ "X-XSRF-TOKEN 인증 값으로 입력한 뒤 상태 변경 API를 호출합니다.")
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "204",
					description = "CSRF 토큰 발급 완료",
					headers = @Header(
							name = "Set-Cookie",
							description = "브라우저에서 읽을 수 있는 XSRF-TOKEN 쿠키",
							schema = @Schema(type = "string")),
					content = @Content)
	})
	ResponseEntity<Void> csrf(@Parameter(hidden = true) CsrfToken csrfToken);

	@Operation(
			summary = "관리자 로그인",
			description = "관리자 세션을 생성합니다. 먼저 CSRF 토큰을 발급받아 쿠키와 "
					+ "동일한 값을 X-XSRF-TOKEN 헤더로 전송해야 합니다.",
			security = @SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "로그인 성공", useReturnTypeSchema = true,
					content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "요청 값 검증 실패",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "로그인 정보 불일치",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "CSRF 토큰 누락 또는 불일치",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "429", description = "로그인 시도 횟수 초과",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "인증 또는 데이터베이스 일시 장애",
					content = @Content(
							mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminResponse>> login(
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "관리자 로그인 정보",
					required = true,
					content = @Content(schema = @Schema(implementation = AdminLoginRequest.class)))
			AdminLoginRequest body,
			@Parameter(hidden = true) HttpServletRequest request,
			@Parameter(hidden = true) HttpServletResponse response);
}
