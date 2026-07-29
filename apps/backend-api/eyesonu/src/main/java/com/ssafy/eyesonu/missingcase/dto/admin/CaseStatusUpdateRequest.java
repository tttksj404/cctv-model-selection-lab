package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;

public record CaseStatusUpdateRequest(
		@NotNull CaseStatus status,
		@NotBlank @Size(max = 1000) String reason) {
}
