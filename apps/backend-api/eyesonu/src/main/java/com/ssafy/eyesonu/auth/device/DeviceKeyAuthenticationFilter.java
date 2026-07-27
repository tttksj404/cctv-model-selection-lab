package com.ssafy.eyesonu.auth.device;

import com.ssafy.eyesonu.auth.security.SecurityErrorWriter;
import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import org.springframework.dao.DataAccessException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.context.SecurityContext;
import org.springframework.security.core.context.SecurityContextHolder;
import org.springframework.web.filter.OncePerRequestFilter;

public class DeviceKeyAuthenticationFilter extends OncePerRequestFilter {

	public static final String HEADER_NAME = "X-Device-Key";
	private static final SimpleGrantedAuthority MEDIA_SERVER_AUTHORITY =
			new SimpleGrantedAuthority("ROLE_MEDIA_SERVER");

	private final MediaServerAuthenticationService authenticationService;
	private final SecurityErrorWriter errors;

	public DeviceKeyAuthenticationFilter(
			MediaServerAuthenticationService authenticationService,
			SecurityErrorWriter errors) {
		this.authenticationService = authenticationService;
		this.errors = errors;
	}

	@Override
	protected void doFilterInternal(
			HttpServletRequest request,
			HttpServletResponse response,
			FilterChain filterChain) throws ServletException, IOException {
		String header = request.getHeader(HEADER_NAME);
		if (header == null || header.isBlank()) {
			errors.write(response, 401, "AUTHENTICATION_REQUIRED", "미디어 서버 인증이 필요합니다.");
			return;
		}

		DeviceKey deviceKey = DeviceKey.parse(header).orElse(null);
		if (deviceKey == null) {
			errors.write(response, 401, "INVALID_DEVICE_KEY", "유효하지 않은 Device Key입니다.");
			return;
		}

		try {
			MediaServerPrincipal principal = authenticationService.authenticate(deviceKey).orElse(null);
			if (principal == null) {
				errors.write(response, 401, "INVALID_DEVICE_KEY", "유효하지 않은 Device Key입니다.");
				return;
			}

			UsernamePasswordAuthenticationToken authentication =
					new UsernamePasswordAuthenticationToken(
							principal, null, List.of(MEDIA_SERVER_AUTHORITY));
			SecurityContext context = SecurityContextHolder.createEmptyContext();
			context.setAuthentication(authentication);
			SecurityContextHolder.setContext(context);
			filterChain.doFilter(request, response);
		} catch (DataAccessException exception) {
			errors.write(
					response,
					503,
					"AUTHENTICATION_UNAVAILABLE",
					"미디어 서버 인증을 일시적으로 처리할 수 없습니다.");
		}
	}
}
