package com.ssafy.eyesonu.auth.dto;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record AdminLoginRequest(
		@NotBlank @Size(max = 50) String loginId,
		@NotBlank @Size(max = 128) String password) {
}
