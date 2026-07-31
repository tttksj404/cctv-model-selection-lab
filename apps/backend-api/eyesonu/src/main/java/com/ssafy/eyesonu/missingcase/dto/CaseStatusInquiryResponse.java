package com.ssafy.eyesonu.missingcase.dto;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import java.time.Instant;

public record CaseStatusInquiryResponse(
		String caseNumber,
		CaseStatus status,
		Instant reportedAt,
		Instant updatedAt,
		Instant closedAt) {
}
