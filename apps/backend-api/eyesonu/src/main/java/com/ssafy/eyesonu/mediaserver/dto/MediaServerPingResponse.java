package com.ssafy.eyesonu.mediaserver.dto;

public record MediaServerPingResponse(
		boolean authenticated,
		Long mediaServerId,
		String serverCode) {
}
