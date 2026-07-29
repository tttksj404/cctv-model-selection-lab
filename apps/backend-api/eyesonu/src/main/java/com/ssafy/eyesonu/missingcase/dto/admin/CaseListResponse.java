package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import java.time.Instant;

public record CaseListResponse(
		Long id,
		String caseNumber,
		CaseStatus status,
		String missingName,
		Gender gender,
		Integer birthYear,
		String photoUrl,
		Instant lastSeenTime,
		String lastSeenAddress,
		Instant reportedAt,
		Instant updatedAt) {

	public static CaseListResponse from(MissingCaseRow row, String photoUrl) {
		return new CaseListResponse(
				row.getId(), row.getCaseNumber(), row.getStatus(), row.getMissingName(),
				row.getGender(), row.getBirthYear(), photoUrl, row.getLastSeenTime(),
				row.getLastSeenAddress(), row.getReportedAt(), row.getUpdatedAt());
	}
}
