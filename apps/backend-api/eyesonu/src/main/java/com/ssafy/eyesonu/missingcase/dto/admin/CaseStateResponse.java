package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import java.time.Instant;

public record CaseStateResponse(
		Long id,
		CaseStatus status,
		Instant closedAt,
		Instant updatedAt) {
}
