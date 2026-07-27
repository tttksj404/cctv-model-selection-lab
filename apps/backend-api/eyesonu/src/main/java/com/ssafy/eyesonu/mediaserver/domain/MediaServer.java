package com.ssafy.eyesonu.mediaserver.domain;

public record MediaServer(
		Long id,
		String serverCode,
		String name,
		String deviceKeyId,
		String deviceKeyHash,
		String status) {

	public boolean isActive() {
		return "ACTIVE".equals(status);
	}
}
