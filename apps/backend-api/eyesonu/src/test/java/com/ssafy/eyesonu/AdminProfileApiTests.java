package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.dto.AdminUpdateRequest;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.service.AdminService;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import com.ssafy.eyesonu.admin.controller.AdminController;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AdminProfileApiTests {

	private static final AdminPrincipal PRINCIPAL = new AdminPrincipal(1L, "admin");

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminService adminService;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditService auditService;

	@MockitoBean
	private MediaServerAuthenticationService mediaServerAuthenticationService;

	@Test
	void nameUpdateReturnsUpdatedProfileWithoutReauthentication() throws Exception {
		AdminUpdateRequest request = new AdminUpdateRequest("Updated Admin", null, null);
		when(adminService.update(eq(PRINCIPAL), eq(request)))
				.thenReturn(new AdminService.UpdateResult(
						new Admin(1L, "admin", "hash", "Updated Admin"), false));

		mockMvc.perform(patch("/api/v1/admins/me")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"name\":\"Updated Admin\"}"))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.admin.id").value(1))
				.andExpect(jsonPath("$.data.admin.name").value("Updated Admin"))
				.andExpect(jsonPath("$.data.reauthenticationRequired").value(false));

		verify(adminService).update(eq(PRINCIPAL), eq(request));
	}

	@Test
	void passwordUpdateReturnsReauthenticationRequired() throws Exception {
		AdminUpdateRequest request = new AdminUpdateRequest(
				null, "current-password!", "new-password!!");
		when(adminService.update(eq(PRINCIPAL), eq(request)))
				.thenReturn(new AdminService.UpdateResult(
						new Admin(1L, "admin", "changed-hash", "Admin"), true));

		mockMvc.perform(patch("/api/v1/admins/me")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
						{"currentPassword":"current-password!","newPassword":"new-password!!"}
						"""))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.admin.name").value("Admin"))
				.andExpect(jsonPath("$.data.reauthenticationRequired").value(true));

		verify(adminService).update(eq(PRINCIPAL), eq(request));
		verify(adminService).expireSessions(eq(PRINCIPAL));
	}

	@Test
	void wrongCurrentPasswordReturnsStructuredBadRequest() throws Exception {
		AdminUpdateRequest request = new AdminUpdateRequest(
				null, "wrong-password!", "new-password!!");
		when(adminService.update(eq(PRINCIPAL), eq(request))).thenThrow(
				new ApiException(HttpStatus.BAD_REQUEST,
						"CURRENT_PASSWORD_MISMATCH", "Current password is incorrect"));

		mockMvc.perform(patch("/api/v1/admins/me")
					.with(adminAuthentication())
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("""
						{"currentPassword":"wrong-password!","newPassword":"new-password!!"}
						"""))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("CURRENT_PASSWORD_MISMATCH"));
	}

	@Test
	void profileUpdateRequiresCsrf() throws Exception {
		mockMvc.perform(patch("/api/v1/admins/me")
					.with(adminAuthentication())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"name\":\"Updated Admin\"}"))
				.andExpect(status().isForbidden())
				.andExpect(jsonPath("$.code").value("ACCESS_DENIED"));

		verifyNoInteractions(adminService);
	}

	private RequestPostProcessor adminAuthentication() {
		return authentication(new UsernamePasswordAuthenticationToken(
				PRINCIPAL, null, PRINCIPAL.getAuthorities()));
	}
}
