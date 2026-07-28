package com.ssafy.eyesonu.common.api;

import java.time.Instant;

public record PagedApiResponse<T>(Instant timestamp, T data, PageMeta meta) {

	public static <T> PagedApiResponse<T> of(T data, PageMeta meta) {
		return new PagedApiResponse<>(Instant.now(), data, meta);
	}
}
