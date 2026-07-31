package com.ssafy.eyesonu;

import static org.mockito.Mockito.when;
import static org.springframework.security.test.web.servlet.request.SecurityMockMvcRequestPostProcessors.authentication;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.config.SecurityConfig;
import com.ssafy.eyesonu.auth.device.MediaServerAuthenticationService;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.GlobalExceptionHandler;
import com.ssafy.eyesonu.mediaserver.controller.admin.AdminMediaServerController;
import com.ssafy.eyesonu.mediaserver.dto.MediaServerOptionResponse;
import com.ssafy.eyesonu.mediaserver.service.MediaServerQueryService;
import java.util.List;
import java.util.Optional;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.webmvc.test.autoconfigure.WebMvcTest;
import org.springframework.context.annotation.Import;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.request.RequestPostProcessor;

@ActiveProfiles("test")
@WebMvcTest(controllers = AdminMediaServerController.class)
@Import({SecurityConfig.class, GlobalExceptionHandler.class})
class MediaServerOptionApiTests {

	@Autowired
	private MockMvc mockMvc;

	@MockitoBean
	private AdminMapper adminMapper;

	@MockitoBean
	private AuditService auditService;

	@MockitoBean
	private MediaServerAuthenticationService mediaServerAuthenticationService;

	@MockitoBean
	private MediaServerQueryService mediaServerQueryService;

	@BeforeEach
	void activeAdmin() {
		when(adminMapper.findById(1L))
				.thenReturn(Optional.of(new Admin(1L, "admin", "hash", "Admin")));
	}

	@Test
	void optionsRequireAdminSession() throws Exception {
		mockMvc.perform(get("/api/v1/admin/media-servers/options"))
				.andExpect(status().isUnauthorized())
				.andExpect(jsonPath("$.code").value("AUTHENTICATION_REQUIRED"));
	}

	@Test
	void optionsDoNotRequireCsrfAndExposeOnlySafeOrderedFields() throws Exception {
		when(mediaServerQueryService.findActiveOptions()).thenReturn(List.of(
				new MediaServerOptionResponse(2L, "media-a", "Media Server A"),
				new MediaServerOptionResponse(7L, "media-z", "Media Server Z")));

		mockMvc.perform(get("/api/v1/admin/media-servers/options").with(adminAuthentication()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data.length()").value(2))
				.andExpect(jsonPath("$.data[0].id").value(2))
				.andExpect(jsonPath("$.data[0].serverCode").value("media-a"))
				.andExpect(jsonPath("$.data[0].name").value("Media Server A"))
				.andExpect(jsonPath("$.data[1].serverCode").value("media-z"))
				.andExpect(jsonPath("$.data[0].deviceKeyId").doesNotExist())
				.andExpect(jsonPath("$.data[0].deviceKeyHash").doesNotExist())
				.andExpect(jsonPath("$.data[0].status").doesNotExist());
	}

	@Test
	void optionsReturnEmptyArrayWhenNoActiveServerExists() throws Exception {
		when(mediaServerQueryService.findActiveOptions()).thenReturn(List.of());

		mockMvc.perform(get("/api/v1/admin/media-servers/options").with(adminAuthentication()))
				.andExpect(status().isOk())
				.andExpect(jsonPath("$.data").isArray())
				.andExpect(jsonPath("$.data").isEmpty());
	}

	private RequestPostProcessor adminAuthentication() {
		AdminPrincipal principal = new AdminPrincipal(1L, "admin");
		return authentication(new UsernamePasswordAuthenticationToken(
				principal, null, principal.getAuthorities()));
	}
}
