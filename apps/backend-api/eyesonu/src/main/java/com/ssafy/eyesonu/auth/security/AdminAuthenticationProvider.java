package com.ssafy.eyesonu.auth.security;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import java.util.Locale;
import org.springframework.security.authentication.AuthenticationProvider;
import org.springframework.security.authentication.BadCredentialsException;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.core.Authentication;
import org.springframework.security.core.AuthenticationException;
import org.springframework.security.crypto.password.PasswordEncoder;

public class AdminAuthenticationProvider implements AuthenticationProvider {

	private final AdminMapper adminMapper;
	private final PasswordEncoder passwordEncoder;
	private final String dummyPasswordHash;

	public AdminAuthenticationProvider(AdminMapper adminMapper, PasswordEncoder passwordEncoder) {
		this.adminMapper = adminMapper;
		this.passwordEncoder = passwordEncoder;
		this.dummyPasswordHash = passwordEncoder.encode("dummy-password-never-used");
	}

	@Override
	public Authentication authenticate(Authentication authentication) throws AuthenticationException {
		String loginId = normalizeLoginId(authentication.getName());
		String password = String.valueOf(authentication.getCredentials());

		Admin admin = adminMapper.findByLoginId(loginId).orElse(null);
		if (admin == null) {
			passwordEncoder.matches(password, dummyPasswordHash);
			throw new BadCredentialsException("Invalid credentials");
		}
		if (!passwordEncoder.matches(password, admin.passwordHash())) {
			throw new BadCredentialsException("Invalid credentials");
		}

		AdminPrincipal principal = new AdminPrincipal(admin.id(), admin.loginId());
		return UsernamePasswordAuthenticationToken.authenticated(
				principal, null, principal.getAuthorities());
	}

	@Override
	public boolean supports(Class<?> authentication) {
		return UsernamePasswordAuthenticationToken.class.isAssignableFrom(authentication);
	}

	public static String normalizeLoginId(String loginId) {
		return loginId == null ? "" : loginId.trim().toLowerCase(Locale.ROOT);
	}
}
