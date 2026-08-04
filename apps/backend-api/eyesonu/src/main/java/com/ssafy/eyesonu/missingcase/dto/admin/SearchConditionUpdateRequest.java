package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.Size;
import java.time.OffsetDateTime;

public record SearchConditionUpdateRequest(
		@Size(max = 4000) String prompt,
		@Size(max = 4000) String exclusionPrompt,
		OffsetDateTime searchStart,
		OffsetDateTime searchEnd,
		@Size(max = 255) String searchArea) {
}
