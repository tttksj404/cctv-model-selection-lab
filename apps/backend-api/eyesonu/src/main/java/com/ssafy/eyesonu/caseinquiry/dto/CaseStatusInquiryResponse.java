package com.ssafy.eyesonu.caseinquiry.dto;

import java.time.Instant;

public record CaseStatusInquiryResponse(
		String caseNumber,
		String status,
		Instant reportedAt,
		Instant updatedAt,
		Instant closedAt) {
}
