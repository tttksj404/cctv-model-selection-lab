package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import java.time.Instant;

public record SearchConditionResponse(
		Long id,
		Long caseId,
		String prompt,
		String exclusionPrompt,
		Instant searchStart,
		Instant searchEnd,
		String searchArea,
		String normalizedPrompt,
		String normalizedExclusionPrompt,
		boolean realtimeUsable,
		Instant createdAt,
		Instant updatedAt) {

	public static SearchConditionResponse from(
			SearchConditionRow row,
			String normalizedPrompt,
			String normalizedExclusionPrompt,
			boolean realtimeUsable) {
		return new SearchConditionResponse(row.getId(), row.getCaseId(), row.getPrompt(),
				row.getExclusionPrompt(), row.getSearchStart(), row.getSearchEnd(), row.getSearchArea(),
				normalizedPrompt, normalizedExclusionPrompt, realtimeUsable,
				row.getCreatedAt(), row.getUpdatedAt());
	}
}
