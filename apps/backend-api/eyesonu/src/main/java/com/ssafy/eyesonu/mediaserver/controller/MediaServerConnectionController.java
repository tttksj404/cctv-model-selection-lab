package com.ssafy.eyesonu.mediaserver.controller;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.mediaserver.dto.MediaServerPingResponse;
import io.swagger.v3.oas.annotations.Hidden;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@Hidden
@RestController
@RequestMapping("/api/v1/device/media-server")
public class MediaServerConnectionController {

	@GetMapping("/ping")
	public ResponseEntity<ApiResponse<MediaServerPingResponse>> ping(
			@AuthenticationPrincipal MediaServerPrincipal principal) {
		return ResponseEntity.ok()
				.cacheControl(CacheControl.noStore())
				.body(ApiResponse.of(new MediaServerPingResponse(
						true, principal.mediaServerId(), principal.serverCode())));
	}
}
