package com.ssafy.eyesonu.auth.controller;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.when;
import static org.mockito.ArgumentMatchers.anyString;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.audit.service.AuditService;
import com.ssafy.eyesonu.auth.dto.AdminLoginRequest;
import com.ssafy.eyesonu.auth.ratelimit.AttemptRateLimiter;
import com.ssafy.eyesonu.auth.security.AdminPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.web.authentication.session.SessionAuthenticationStrategy;
import org.springframework.security.web.context.SecurityContextRepository;

class AuthControllerTests {

	@Test
	void rechecksDisabledStateBeforeRegisteringAuthenticatedSession() {
		AuthenticationManager authenticationManager = mock(AuthenticationManager.class);
		SessionAuthenticationStrategy sessionStrategy = mock(SessionAuthenticationStrategy.class);
		SecurityContextRepository contextRepository = mock(SecurityContextRepository.class);
		AdminMapper adminMapper = mock(AdminMapper.class);
		AttemptRateLimiter rateLimiter = mock(AttemptRateLimiter.class);
		AuditService auditService = mock(AuditService.class);
		AuthController controller = new AuthController(
				authenticationManager,
				sessionStrategy,
				contextRepository,
				adminMapper,
				rateLimiter,
				auditService);
		AdminPrincipal principal = new AdminPrincipal(1L, "admin", AdminRole.ADMIN);
		when(rateLimiter.isAllowed("admin-login", "127.0.0.1", "admin")).thenReturn(true);
		when(rateLimiter.fingerprint(anyString())).thenReturn("fingerprint");
		when(authenticationManager.authenticate(org.mockito.ArgumentMatchers.any()))
				.thenReturn(UsernamePasswordAuthenticationToken.authenticated(
						principal, null, principal.getAuthorities()));
		when(adminMapper.findById(1L)).thenReturn(Optional.of(new Admin(
				1L,
				"admin",
				"hash",
				"Administrator",
				AdminRole.ADMIN,
				false,
				Instant.parse("2026-07-31T00:00:00Z"))));
		MockHttpServletRequest request = new MockHttpServletRequest();
		request.setRemoteAddr("127.0.0.1");

		ApiException exception = assertThrows(ApiException.class, () -> controller.login(
				new AdminLoginRequest("admin", "correct-password!"),
				request,
				new MockHttpServletResponse()));

		assertEquals("INVALID_CREDENTIALS", exception.getCode());
		verifyNoInteractions(sessionStrategy, contextRepository);
	}
}
