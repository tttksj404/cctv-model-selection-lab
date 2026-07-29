package com.ssafy.eyesonu.missingcase.domain;

public record CasePhotoState(
		Long id,
		CaseStatus status,
		String photoS3Key) {
}
