package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import java.time.OffsetDateTime;

public record CaseSearchCondition(
		CaseStatus status,
		String caseNumber,
		String missingName,
		OffsetDateTime reportedFrom,
		OffsetDateTime reportedTo,
		int page,
		int size,
		String sort) {
}
