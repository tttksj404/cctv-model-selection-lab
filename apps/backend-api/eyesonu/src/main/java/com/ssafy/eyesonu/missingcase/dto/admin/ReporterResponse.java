package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;

public record ReporterResponse(
		Long id,
		String name,
		String phone,
		String email,
		String relation) {

	public static ReporterResponse from(MissingCaseRow row) {
		return new ReporterResponse(
				row.getReporterId(), row.getReporterName(), row.getReporterPhone(),
				row.getReporterEmail(), row.getReporterRelation());
	}
}
