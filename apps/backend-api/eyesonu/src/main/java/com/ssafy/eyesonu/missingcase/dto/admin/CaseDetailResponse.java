package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import java.math.BigDecimal;
import java.time.Instant;

public record CaseDetailResponse(
		Long id,
		String caseNumber,
		CaseStatus status,
		ReporterResponse reporter,
		String reportContent,
		String missingName,
		Gender gender,
		Integer birthYear,
		AppearanceResponse appearance,
		String photoUrl,
		Instant lastSeenTime,
		BigDecimal lastSeenLat,
		BigDecimal lastSeenLng,
		String lastSeenAddress,
		Instant reportedAt,
		Instant closedAt,
		Instant updatedAt) {

	public static CaseDetailResponse from(MissingCaseRow row, String photoUrl) {
		return new CaseDetailResponse(
				row.getId(), row.getCaseNumber(), row.getStatus(), ReporterResponse.from(row),
				row.getReportContent(), row.getMissingName(), row.getGender(), row.getBirthYear(),
				AppearanceResponse.from(row), photoUrl, row.getLastSeenTime(), row.getLastSeenLat(),
				row.getLastSeenLng(), row.getLastSeenAddress(), row.getReportedAt(),
				row.getClosedAt(), row.getUpdatedAt());
	}
}
