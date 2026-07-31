package com.ssafy.eyesonu.auth.security;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import jakarta.servlet.FilterChain;
import java.time.Instant;
import java.util.Optional;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.context.SecurityContextHolder;
import tools.jackson.databind.json.JsonMapper;

class AdminAccountStatusFilterTests {

	private AdminMapper adminMapper;
	private AdminAccountStatusFilter filter;
	private FilterChain filterChain;
	private MockHttpServletRequest request;
	private MockHttpServletResponse response;
	private MockHttpSession session;

	@BeforeEach
	void setUp() {
		adminMapper = mock(AdminMapper.class);
		filter = new AdminAccountStatusFilter(adminMapper, JsonMapper.builder().build());
		filterChain = mock(FilterChain.class);
		request = new MockHttpServletRequest("GET", "/api/v1/admin/cases");
		response = new MockHttpServletResponse();
		session = (MockHttpSession) request.getSession(true);

		AdminPrincipal principal = new AdminPrincipal(1L, "admin", AdminRole.ADMIN);
		SecurityContextHolder.getContext().setAuthentication(
				UsernamePasswordAuthenticationToken.authenticated(
						principal, null, principal.getAuthorities()));
	}

	@AfterEach
	void tearDown() {
		SecurityContextHolder.clearContext();
	}

	@Test
	void activeAdministratorContinuesTheProtectedRequest() throws Exception {
		when(adminMapper.findById(1L)).thenReturn(Optional.of(admin(true)));

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		assertFalse(session.isInvalid());
	}

	@Test
	void disabledAdministratorIsLoggedOutAndBlocked() throws Exception {
		when(adminMapper.findById(1L)).thenReturn(Optional.of(admin(false)));

		filter.doFilter(request, response, filterChain);

		verify(filterChain, never()).doFilter(request, response);
		assertEquals(401, response.getStatus());
		assertTrue(response.getContentAsString().contains("AUTHENTICATION_REQUIRED"));
		assertTrue(session.isInvalid());
	}

	@Test
	void deletedAdministratorIsLoggedOutAndBlocked() throws Exception {
		when(adminMapper.findById(1L)).thenReturn(Optional.empty());

		filter.doFilter(request, response, filterChain);

		verify(filterChain, never()).doFilter(request, response);
		assertEquals(401, response.getStatus());
		assertTrue(response.getContentAsString().contains("AUTHENTICATION_REQUIRED"));
		assertTrue(session.isInvalid());
	}

	@Test
	void databaseFailureBlocksRequestWithoutDestroyingSession() throws Exception {
		when(adminMapper.findById(1L))
				.thenThrow(new DataAccessResourceFailureException("database unavailable"));

		filter.doFilter(request, response, filterChain);

		verify(filterChain, never()).doFilter(request, response);
		assertEquals(503, response.getStatus());
		assertTrue(response.getContentAsString().contains("DATABASE_UNAVAILABLE"));
		assertFalse(session.isInvalid());
	}

	@Test
	void staleSessionDoesNotBlockPublicLoginEndpoint() throws Exception {
		request = new MockHttpServletRequest("POST", "/api/v1/auth/admin/login");

		filter.doFilter(request, response, filterChain);

		verify(filterChain).doFilter(request, response);
		verify(adminMapper, never()).findById(1L);
	}

	private Admin admin(boolean enabled) {
		return new Admin(
				1L,
				"admin",
				"hash",
				"Administrator",
				AdminRole.ADMIN,
				enabled,
				Instant.parse("2026-07-31T00:00:00Z"));
	}
}
