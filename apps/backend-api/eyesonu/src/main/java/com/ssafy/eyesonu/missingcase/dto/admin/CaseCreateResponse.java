package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import java.time.Instant;

public record CaseCreateResponse(
		Long id,
		String caseNumber,
		CaseStatus status,
		Instant reportedAt) {
}
