package com.ssafy.eyesonu.missingcase.dto.admin;

import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record SearchConditionCreateRequest(
		@NotBlank @Size(max = 4000) String prompt,
		@Size(max = 4000) String exclusionPrompt,
		OffsetDateTime searchStart,
		OffsetDateTime searchEnd,
		@Size(max = 255) String searchArea,
		@NotNull @DecimalMin("0.0") @DecimalMax("1.0") BigDecimal similarityThreshold) {
}
