package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.Gender;
import jakarta.validation.Valid;
import jakarta.validation.constraints.DecimalMax;
import jakarta.validation.constraints.DecimalMin;
import jakarta.validation.constraints.Max;
import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Size;
import java.math.BigDecimal;
import java.time.OffsetDateTime;

public record CaseCreateRequest(
		@NotNull @Valid ReporterRequest reporter,
		@NotBlank @Size(max = 4000) String reportContent,
		@NotBlank @Size(max = 50) String missingName,
		@NotNull Gender gender,
		@Min(1900) @Max(2100) Integer birthYear,
		@NotNull @Valid AppearanceRequest appearance,
		@NotNull OffsetDateTime lastSeenTime,
		@DecimalMin("-90.0") @DecimalMax("90.0") BigDecimal lastSeenLat,
		@DecimalMin("-180.0") @DecimalMax("180.0") BigDecimal lastSeenLng,
		@NotBlank @Size(max = 255) String lastSeenAddress) {
}
