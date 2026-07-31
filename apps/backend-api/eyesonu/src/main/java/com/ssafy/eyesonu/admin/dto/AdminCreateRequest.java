package com.ssafy.eyesonu.admin.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AdminCreateRequest(
		@NotBlank @Size(max = 50) String loginId,
		@NotBlank @Size(max = 50) String name,
		@NotBlank @Size(max = 64) String password) {
}
