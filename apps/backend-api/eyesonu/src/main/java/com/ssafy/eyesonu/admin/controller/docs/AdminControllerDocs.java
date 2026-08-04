package com.ssafy.eyesonu.admin.controller.docs;

import com.ssafy.eyesonu.admin.dto.AdminCreateRequest;
import com.ssafy.eyesonu.admin.dto.AdminManagementResponse;
import com.ssafy.eyesonu.admin.dto.AdminResponse;
import com.ssafy.eyesonu.admin.dto.AdminStatusUpdateRequest;
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
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;

@Tag(name = "관리자", description = "로그인한 관리자 정보와 관리자 계정 관리 API")
public interface AdminControllerDocs {

	@Operation(
			summary = "관리자 계정 목록 조회",
			description = "모든 관리자 계정을 조회합니다. SUPER_ADMIN 권한이 필요합니다.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 계정 목록 조회 성공",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN 권한 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "데이터베이스를 일시적으로 사용할 수 없음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<List<AdminManagementResponse>>> list();

	@Operation(
			summary = "관리자 계정 생성",
			description = "활성화된 ADMIN 계정을 생성합니다. SUPER_ADMIN 권한과 CSRF 토큰이 필요합니다.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "201", description = "관리자 계정 생성 성공",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "관리자 계정 값이 올바르지 않음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN 권한 또는 CSRF 토큰 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "409", description = "로그인 ID가 이미 존재함",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "데이터베이스를 일시적으로 사용할 수 없음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminManagementResponse>> create(
			@Parameter(hidden = true) AdminPrincipal principal,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "관리자 계정 정보", required = true,
					content = @Content(schema = @Schema(implementation = AdminCreateRequest.class)))
			AdminCreateRequest body);

	@Operation(
			summary = "관리자 계정 상태 변경",
			description = "관리자 계정을 활성화하거나 비활성화합니다. SUPER_ADMIN 권한과 CSRF 토큰이 필요합니다.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 계정 상태 변경 성공",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "상태 값이 올바르지 않음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN 권한 또는 CSRF 토큰 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "404", description = "관리자 계정을 찾을 수 없음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "409", description = "계정 상태 불변 조건을 위반하는 변경",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "데이터베이스를 일시적으로 사용할 수 없음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminManagementResponse>> updateStatus(
			@Parameter(hidden = true) AdminPrincipal principal,
			@Parameter(description = "관리자 계정 ID", required = true) Long adminId,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "변경할 활성화 상태", required = true,
					content = @Content(schema = @Schema(implementation = AdminStatusUpdateRequest.class)))
			AdminStatusUpdateRequest body);

	@Operation(
			summary = "현재 관리자 프로필 조회",
			description = "현재 인증된 관리자 프로필을 조회합니다.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 프로필 조회 성공",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminResponse>> me(
			@Parameter(hidden = true) AdminPrincipal principal);

	@Operation(
			summary = "현재 관리자 프로필 수정",
			description = "현재 관리자 이름 또는 비밀번호를 수정합니다.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "관리자 프로필 수정 성공",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "값이 올바르지 않거나 현재 비밀번호가 일치하지 않음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "인증 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "CSRF 토큰 필요",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "관리자 정보 수정 또는 데이터베이스를 일시적으로 사용할 수 없음",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminUpdateResponse>> update(
			@Parameter(hidden = true) AdminPrincipal principal,
			@Parameter(hidden = true) Authentication authentication,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "관리자 프로필 정보", required = true,
					content = @Content(schema = @Schema(implementation = AdminUpdateRequest.class)))
			AdminUpdateRequest body,
			@Parameter(hidden = true) HttpServletRequest request,
			@Parameter(hidden = true) HttpServletResponse response);
}
