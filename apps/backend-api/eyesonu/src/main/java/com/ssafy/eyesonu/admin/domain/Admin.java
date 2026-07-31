package com.ssafy.eyesonu.admin.domain;

import java.time.Instant;

public record Admin(
		Long id,
		String loginId,
		String passwordHash,
		String name,
		AdminRole role,
		boolean enabled,
		Instant createdAt) {

	public Admin(Long id, String loginId, String passwordHash, String name) {
		this(id, loginId, passwordHash, name, AdminRole.ADMIN, true, null);
	}
}
