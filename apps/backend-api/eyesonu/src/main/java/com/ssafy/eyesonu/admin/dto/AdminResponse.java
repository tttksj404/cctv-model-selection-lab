package com.ssafy.eyesonu.admin.dto;

import com.ssafy.eyesonu.admin.domain.Admin;
import com.ssafy.eyesonu.admin.domain.AdminRole;

public record AdminResponse(Long id, String loginId, String name, AdminRole role) {

	public static AdminResponse from(Admin admin) {
		return new AdminResponse(admin.id(), admin.loginId(), admin.name(), admin.role());
	}
}
