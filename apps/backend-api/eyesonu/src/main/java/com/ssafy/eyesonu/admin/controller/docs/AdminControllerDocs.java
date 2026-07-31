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
			summary = "List administrator accounts",
			description = "Returns every administrator account. SUPER_ADMIN authority is required.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "Administrator accounts returned",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "Authentication required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN authority required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "Database temporarily unavailable",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<List<AdminManagementResponse>>> list();

	@Operation(
			summary = "Create an administrator account",
			description = "Creates an enabled ADMIN account. SUPER_ADMIN authority and a CSRF token are required.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "201", description = "Administrator account created",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "Invalid account values",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "Authentication required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN authority or CSRF token required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "409", description = "Login ID already exists",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "Database temporarily unavailable",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminManagementResponse>> create(
			@Parameter(hidden = true) AdminPrincipal principal,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "Administrator account values", required = true,
					content = @Content(schema = @Schema(implementation = AdminCreateRequest.class)))
			AdminCreateRequest body);

	@Operation(
			summary = "Change administrator account status",
			description = "Enables or disables an administrator account. SUPER_ADMIN authority and a CSRF token are required.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "Administrator account status returned",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "Invalid status value",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "Authentication required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "SUPER_ADMIN authority or CSRF token required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "404", description = "Administrator account not found",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "409", description = "Status change would violate account invariants",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "Database temporarily unavailable",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminManagementResponse>> updateStatus(
			@Parameter(hidden = true) AdminPrincipal principal,
			@Parameter(description = "Administrator account ID", required = true) Long adminId,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "Desired enabled state", required = true,
					content = @Content(schema = @Schema(implementation = AdminStatusUpdateRequest.class)))
			AdminStatusUpdateRequest body);

	@Operation(
			summary = "Get current administrator profile",
			description = "Returns the currently authenticated administrator profile.",
			security = @SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME))
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "Administrator profile returned",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "Authentication required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminResponse>> me(
			@Parameter(hidden = true) AdminPrincipal principal);

	@Operation(
			summary = "Update current administrator profile",
			description = "Updates the current administrator name or password.",
			security = {
					@SecurityRequirement(name = SwaggerConfig.SESSION_SCHEME),
					@SecurityRequirement(name = SwaggerConfig.CSRF_SCHEME)
			})
	@ApiResponses({
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "200", description = "Administrator profile updated",
					useReturnTypeSchema = true, content = @Content(mediaType = "application/json")),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "400", description = "Invalid values or current password mismatch",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "401", description = "Authentication required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "403", description = "CSRF token required",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class))),
			@io.swagger.v3.oas.annotations.responses.ApiResponse(
					responseCode = "503", description = "Administrator update or database temporarily unavailable",
					content = @Content(mediaType = "application/json",
							schema = @Schema(implementation = ApiErrorResponse.class)))
	})
	ResponseEntity<ApiResponse<AdminUpdateResponse>> update(
			@Parameter(hidden = true) AdminPrincipal principal,
			@Parameter(hidden = true) Authentication authentication,
			@io.swagger.v3.oas.annotations.parameters.RequestBody(
					description = "Administrator profile values", required = true,
					content = @Content(schema = @Schema(implementation = AdminUpdateRequest.class)))
			AdminUpdateRequest body,
			@Parameter(hidden = true) HttpServletRequest request,
			@Parameter(hidden = true) HttpServletResponse response);
}
