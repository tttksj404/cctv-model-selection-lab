package com.ssafy.eyesonu.missingcase.messaging;

import java.time.Instant;

public record SearchTargetEvent(
		String commandId,
		String eventType,
		Long caseId,
		Instant updatedAt,
		Instant occurredAt) {
}
