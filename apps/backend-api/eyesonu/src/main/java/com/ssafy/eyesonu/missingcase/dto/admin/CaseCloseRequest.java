package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;

public record CaseCloseRequest(
		@NotBlank @Size(max = 1000) String reason,
		boolean force) {
}
