package com.ssafy.eyesonu.admin.dto;

import com.ssafy.eyesonu.admin.domain.Admin;

public record AdminResponse(Long id, String loginId, String name) {

	public static AdminResponse from(Admin admin) {
		return new AdminResponse(admin.id(), admin.loginId(), admin.name());
	}
}
