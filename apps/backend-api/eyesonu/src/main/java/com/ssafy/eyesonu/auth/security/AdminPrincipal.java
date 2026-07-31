package com.ssafy.eyesonu.auth.security;

import com.ssafy.eyesonu.admin.domain.AdminRole;
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

	private static final List<GrantedAuthority> ADMIN_AUTHORITIES =
			List.of(new SimpleGrantedAuthority("ROLE_ADMIN"));
	private static final List<GrantedAuthority> SUPER_ADMIN_AUTHORITIES = List.of(
			new SimpleGrantedAuthority("ROLE_ADMIN"),
			new SimpleGrantedAuthority("ROLE_SUPER_ADMIN"));

	private final Long adminId;
	private final String loginId;
	private final AdminRole role;

	public AdminPrincipal(Long adminId, String loginId) {
		this(adminId, loginId, AdminRole.ADMIN);
	}

	public AdminPrincipal(Long adminId, String loginId, AdminRole role) {
		this.adminId = Objects.requireNonNull(adminId);
		this.loginId = Objects.requireNonNull(loginId);
		this.role = Objects.requireNonNull(role);
	}

	public Long getAdminId() {
		return adminId;
	}

	public String getLoginId() {
		return loginId;
	}

	public AdminRole getRole() {
		return role;
	}

	public Collection<? extends GrantedAuthority> getAuthorities() {
		return role == AdminRole.SUPER_ADMIN ? SUPER_ADMIN_AUTHORITIES : ADMIN_AUTHORITIES;
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
