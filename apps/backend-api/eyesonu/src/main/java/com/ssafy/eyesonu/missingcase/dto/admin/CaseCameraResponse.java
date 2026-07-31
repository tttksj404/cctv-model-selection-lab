package com.ssafy.eyesonu.missingcase.dto.admin;

import com.ssafy.eyesonu.missingcase.domain.CaseCameraRow;
import java.time.Instant;

public record CaseCameraResponse(
		Long id,
		Long caseId,
		Long cameraId,
		String cameraCode,
		String cameraName,
		boolean searchEnabled,
		Instant selectedAt,
		Instant removedAt) {

	public static CaseCameraResponse from(CaseCameraRow row) {
		return new CaseCameraResponse(row.getId(), row.getCaseId(), row.getCameraId(),
				row.getCameraCode(), row.getCameraName(), row.isSearchEnabled(),
				row.getSelectedAt(), row.getRemovedAt());
	}
}
