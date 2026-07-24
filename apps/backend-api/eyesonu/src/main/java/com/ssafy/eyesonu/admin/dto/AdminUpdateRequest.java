package com.ssafy.eyesonu.admin.dto;

import jakarta.validation.constraints.Size;

public record AdminUpdateRequest(
		@Size(max = 50) String name,
		@Size(max = 128) String currentPassword,
		@Size(max = 128) String newPassword) {
}
