package com.ssafy.eyesonu.missingcase.dto.device;

import java.time.Instant;
import java.util.List;

public record SearchTargetResponse(
		Long caseId,
		String caseNumber,
		List<SearchConditionTargetResponse> searchConditions,
		List<SearchCameraTargetResponse> cameras,
		Instant updatedAt) {
}
