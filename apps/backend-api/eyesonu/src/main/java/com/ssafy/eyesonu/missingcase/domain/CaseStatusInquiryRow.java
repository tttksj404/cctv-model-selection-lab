package com.ssafy.eyesonu.missingcase.domain;

import java.time.Instant;

public record CaseStatusInquiryRow(
		Long id,
		String caseNumber,
		CaseStatus status,
		Instant reportedAt,
		Instant updatedAt,
		Instant closedAt) {
}
