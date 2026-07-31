package com.ssafy.eyesonu;

import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.csrf;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.patch;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.header;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;
import static org.hamcrest.Matchers.containsString;

import com.ssafy.eyesonu.admin.controller.AdminController;
import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.dto.AdminCreateRequest;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.service.AdminService;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.http.MediaType;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class AdminManagementApiTests {

	private static final AdminPrincipal SUPER_ADMIN =
			new AdminPrincipal(1L, "root", AdminRole.SUPER_ADMIN);
	private static final AdminPrincipal ADMIN =
			new AdminPrincipal(2L, "admin", AdminRole.ADMIN);

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

	@BeforeEach
	void activeAdmins() {
		when(adminMapper.findById(1L))
				.thenReturn(Optional.of(account(1L, "root", AdminRole.SUPER_ADMIN, true)));
		when(adminMapper.findById(2L))
				.thenReturn(Optional.of(account(2L, "admin", AdminRole.ADMIN, true)));
	}

	@Test
	void superAdminListsAccountsWithoutPasswordMaterial() throws Exception {
		when(adminService.list()).thenReturn(List.of(account(2L, "admin", AdminRole.ADMIN, true)));

		mockMvc.perform(get("/api/v1/admins").with(asAuthentication(SUPER_ADMIN)))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(jsonPath("$.data[0].id").value(2))
				.andExpect(jsonPath("$.data[0].loginId").value("admin"))
				.andExpect(jsonPath("$.data[0].role").value("ADMIN"))
				.andExpect(jsonPath("$.data[0].enabled").value(true))
				.andExpect(jsonPath("$.data[0].createdAt").value("2026-07-31T00:00:00Z"))
				.andExpect(jsonPath("$.data[0].password").doesNotExist())
				.andExpect(jsonPath("$.data[0].passwordHash").doesNotExist());
	}

	@Test
	void regularAdminCannotUseManagementEndpoints() throws Exception {
		mockMvc.perform(get("/api/v1/admins").with(asAuthentication(ADMIN)))
				.andExpect(status().isForbidden())
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(jsonPath("$.code").value("ACCESS_DENIED"));

		mockMvc.perform(post("/api/v1/admins")
					.with(asAuthentication(ADMIN))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content(validCreateBody()))
				.andExpect(status().isForbidden());

		mockMvc.perform(patch("/api/v1/admins/3/status")
					.with(asAuthentication(ADMIN))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"enabled\":false}"))
				.andExpect(status().isForbidden());

		verifyNoInteractions(adminService);
	}

	@Test
	void creatingAdminRequiresCsrfAndReturnsCreatedAdmin() throws Exception {
		AdminCreateRequest request = new AdminCreateRequest(
				"new.admin", "New Admin", "initial-password!");
		when(adminService.create(eq(SUPER_ADMIN), eq(request)))
				.thenReturn(account(10L, "new.admin", AdminRole.ADMIN, true));

		mockMvc.perform(post("/api/v1/admins")
					.with(asAuthentication(SUPER_ADMIN))
					.contentType(MediaType.APPLICATION_JSON)
					.content(validCreateBody()))
				.andExpect(status().isForbidden())
				.andExpect(header().string("Cache-Control", containsString("no-store")));

		mockMvc.perform(post("/api/v1/admins")
					.with(asAuthentication(SUPER_ADMIN))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content(validCreateBody()))
				.andExpect(status().isCreated())
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(jsonPath("$.data.id").value(10))
				.andExpect(jsonPath("$.data.role").value("ADMIN"))
				.andExpect(jsonPath("$.data.enabled").value(true))
				.andExpect(jsonPath("$.data.passwordHash").doesNotExist());

		verify(adminService).create(eq(SUPER_ADMIN), eq(request));
	}

	@Test
	void statusUpdateReturnsCurrentRepresentationAndValidatesEnabled() throws Exception {
		when(adminService.updateStatus(SUPER_ADMIN, 2L, false))
				.thenReturn(account(2L, "admin", AdminRole.ADMIN, false));

		mockMvc.perform(patch("/api/v1/admins/2/status")
					.with(asAuthentication(SUPER_ADMIN))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{\"enabled\":false}"))
				.andExpect(status().isOk())
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(jsonPath("$.data.id").value(2))
				.andExpect(jsonPath("$.data.enabled").value(false));

		mockMvc.perform(patch("/api/v1/admins/2/status")
					.with(asAuthentication(SUPER_ADMIN))
					.with(csrf())
					.contentType(MediaType.APPLICATION_JSON)
					.content("{}"))
				.andExpect(status().isBadRequest())
				.andExpect(jsonPath("$.code").value("VALIDATION_ERROR"));

		verify(adminService).updateStatus(SUPER_ADMIN, 2L, false);
	}

	@Test
	void unauthenticatedManagementRequestReturnsJson401AndNoStore() throws Exception {
		mockMvc.perform(get("/api/v1/admins"))
				.andExpect(status().isUnauthorized())
				.andExpect(header().string("Cache-Control", containsString("no-store")))
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	private RequestPostProcessor asAuthentication(AdminPrincipal principal) {
		return authentication(new UsernamePasswordAuthenticationToken(
				principal, null, principal.getAuthorities()));
	}

	private Admin account(Long id, String loginId, AdminRole role, boolean enabled) {
		return new Admin(
				id,
				loginId,
				"never-serialized",
				"Admin",
				role,
				enabled,
				Instant.parse("2026-07-31T00:00:00Z"));
	}

	private String validCreateBody() {
		return """
				{"loginId":"new.admin","name":"New Admin","password":"initial-password!"}
				""";
	}
}
