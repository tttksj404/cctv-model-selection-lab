package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Pattern;
import jakarta.validation.constraints.Size;

public record ReporterRequest(
		@NotBlank @Size(max = 50) String name,
		@NotBlank @Size(max = 30)
		@Pattern(regexp = "[0-9 -]+", message = "숫자, 하이픈, 공백만 사용할 수 있습니다.")
		String phone,
		@Email @Size(max = 100) String email,
		@Size(max = 50) String relation) {
}
