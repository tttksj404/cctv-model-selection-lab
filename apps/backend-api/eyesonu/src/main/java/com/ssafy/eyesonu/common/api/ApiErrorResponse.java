package com.ssafy.eyesonu.common.api;

import java.time.Instant;

public record ApiErrorResponse(
		Instant timestamp,
		int status,
		String code,
		String message) {

	public static ApiErrorResponse of(int status, String code, String message) {
		return new ApiErrorResponse(Instant.now(), status, code, message);
	}
}
