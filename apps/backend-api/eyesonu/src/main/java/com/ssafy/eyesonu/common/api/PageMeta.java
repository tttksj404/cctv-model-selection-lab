package com.ssafy.eyesonu.common.api;

public record PageMeta(
		int page,
		int size,
		long totalElements,
		int totalPages,
		String sort) {
}
