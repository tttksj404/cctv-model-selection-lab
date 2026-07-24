package com.ssafy.eyesonu.auth.security;

import java.io.Serial;
import java.io.Serializable;
import java.util.Collection;
import java.util.List;
import java.util.Objects;
import org.springframework.security.core.GrantedAuthority;
import org.springframework.security.core.authority.SimpleGrantedAuthority;

public final class AdminPrincipal implements Serializable {

	@Serial
	private static final long serialVersionUID = 1L;

	private static final List<GrantedAuthority> AUTHORITIES =
			List.of(new SimpleGrantedAuthority("ROLE_ADMIN"));

	private final Long adminId;
	private final String loginId;

	public AdminPrincipal(Long adminId, String loginId) {
		this.adminId = Objects.requireNonNull(adminId);
		this.loginId = Objects.requireNonNull(loginId);
	}

	public Long getAdminId() {
		return adminId;
	}

	public String getLoginId() {
		return loginId;
	}

	public Collection<? extends GrantedAuthority> getAuthorities() {
		return AUTHORITIES;
	}

	@Override
	public boolean equals(Object other) {
		return this == other
				|| (other instanceof AdminPrincipal principal && adminId.equals(principal.adminId));
	}

	@Override
	public int hashCode() {
		return adminId.hashCode();
	}
}
