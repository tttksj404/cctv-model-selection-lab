package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import java.math.BigDecimal;
import java.time.Instant;

public record SearchConditionResponse(
		Long id,
		Long caseId,
		String prompt,
		String exclusionPrompt,
		Instant searchStart,
		Instant searchEnd,
		String searchArea,
		BigDecimal similarityThreshold,
		Instant createdAt,
		Instant updatedAt) {

	public static SearchConditionResponse from(SearchConditionRow row) {
		return new SearchConditionResponse(row.getId(), row.getCaseId(), row.getPrompt(),
				row.getExclusionPrompt(), row.getSearchStart(), row.getSearchEnd(), row.getSearchArea(),
				row.getSimilarityThreshold(), row.getCreatedAt(), row.getUpdatedAt());
	}
}
