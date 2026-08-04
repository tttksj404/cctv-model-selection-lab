package com.ssafy.eyesonu.missingcase.dto.device;

import java.time.Instant;

public record SearchConditionTargetResponse(
		Long conditionId,
		String prompt,
		String exclusionPrompt,
		Instant searchStart,
		Instant searchEnd,
		String searchArea) {
}
