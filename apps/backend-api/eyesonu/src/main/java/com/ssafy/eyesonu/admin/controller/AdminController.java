package com.ssafy.eyesonu.admin.controller;

import com.ssafy.eyesonu.admin.dto.AdminResponse;
import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.dto.AdminUpdateResponse;
import com.ssafy.eyesonu.admin.controller.docs.AdminControllerDocs;
import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.service.AdminService;
import com.ssafy.eyesonu.admin.service.AdminService.UpdateResult;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import jakarta.validation.Valid;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.security.web.authentication.logout.CookieClearingLogoutHandler;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PatchMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admins")
public class AdminController implements AdminControllerDocs {

	private final AdminService adminService;

	public AdminController(AdminService adminService) {
		this.adminService = adminService;
	}

	@GetMapping("/me")
	@Override
	public ResponseEntity<ApiResponse<AdminResponse>> me(
			@AuthenticationPrincipal AdminPrincipal principal) {
		Admin admin = adminService.get(principal.getAdminId());
		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(AdminResponse.from(admin)));
	}

	@PatchMapping("/me")
	@Override
	public ResponseEntity<ApiResponse<AdminUpdateResponse>> update(
			@AuthenticationPrincipal AdminPrincipal principal,
			Authentication authentication,
			@Valid @RequestBody AdminUpdateRequest body,
			HttpServletRequest request,
			HttpServletResponse response) {
		UpdateResult result = adminService.update(principal, body);
		if (result.passwordChanged()) {
			adminService.expireSessions(principal);
			new SecurityContextLogoutHandler().logout(request, response, authentication);
			new CookieClearingLogoutHandler("EYESONU_SESSION", "XSRF-TOKEN")
					.logout(request, response, authentication);
		}
		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(new AdminUpdateResponse(
						AdminResponse.from(result.admin()), result.passwordChanged())));
	}
}
