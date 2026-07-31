package com.ssafy.eyesonu.admin.dto;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import java.time.Instant;

public record AdminManagementResponse(
		Long id,
		String loginId,
		String name,
		AdminRole role,
		boolean enabled,
		Instant createdAt) {

	public static AdminManagementResponse from(Admin admin) {
		return new AdminManagementResponse(
				admin.id(),
				admin.loginId(),
				admin.name(),
				admin.role(),
				admin.enabled(),
				admin.createdAt());
	}
}
