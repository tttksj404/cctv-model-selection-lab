package com.ssafy.eyesonu.auth.security;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.Optional;
import org.springframework.dao.DataAccessException;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.security.web.authentication.logout.CookieClearingLogoutHandler;
import org.springframework.security.web.authentication.logout.SecurityContextLogoutHandler;
import org.springframework.web.filter.OncePerRequestFilter;
import tools.jackson.databind.ObjectMapper;

public class AdminAccountStatusFilter extends OncePerRequestFilter {

	private final AdminMapper adminMapper;
	private final SecurityErrorWriter errors;
	private final SecurityContextLogoutHandler securityContextLogoutHandler =
			new SecurityContextLogoutHandler();
	private final CookieClearingLogoutHandler cookieClearingLogoutHandler =
			new CookieClearingLogoutHandler("EYESONU_SESSION", "XSRF-TOKEN");

	public AdminAccountStatusFilter(AdminMapper adminMapper, ObjectMapper objectMapper) {
		this.adminMapper = adminMapper;
		this.errors = new SecurityErrorWriter(objectMapper);
	}

	@Override
	protected boolean shouldNotFilter(HttpServletRequest request) {
		String uri = request.getRequestURI();
		return !(uri.equals("/api/v1/admin")
				|| uri.startsWith("/api/v1/admin/")
				|| uri.equals("/api/v1/admins")
				|| uri.startsWith("/api/v1/admins/"));
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain) throws ServletException, IOException {
		Authentication authentication = SecurityContextHolder.getContext().getAuthentication();
		if (authentication == null
				|| !authentication.isAuthenticated()
				|| !(authentication.getPrincipal() instanceof AdminPrincipal principal)) {
			filterChain.doFilter(request, response);
			return;
		}

		Optional<Admin> admin;
		try {
			admin = adminMapper.findById(principal.getAdminId());
		}
		catch (DataAccessException exception) {
			response.setHeader("Cache-Control", "no-store");
			errors.write(
					response,
					HttpServletResponse.SC_SERVICE_UNAVAILABLE,
					"DATABASE_UNAVAILABLE",
					"관리자 계정 상태를 확인할 수 없습니다.");
			return;
		}

		if (admin == null || admin.isEmpty() || !admin.orElseThrow().enabled()) {
			securityContextLogoutHandler.logout(request, response, authentication);
			cookieClearingLogoutHandler.logout(request, response, authentication);
			response.setHeader("Cache-Control", "no-store");
			errors.write(
					response,
					HttpServletResponse.SC_UNAUTHORIZED,
					"AUTHENTICATION_REQUIRED",
					"인증이 필요합니다.");
			return;
		}

		filterChain.doFilter(request, response);
	}
}
