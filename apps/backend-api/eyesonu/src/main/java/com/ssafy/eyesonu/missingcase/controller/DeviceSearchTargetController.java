package com.ssafy.eyesonu.missingcase.controller;

import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.missingcase.dto.device.SearchTargetResponse;
import com.ssafy.eyesonu.missingcase.service.DeviceSearchTargetService;
import java.util.List;
import java.time.Instant;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.security.core.annotation.AuthenticationPrincipal;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/device")
public class DeviceSearchTargetController {

	private final DeviceSearchTargetService service;

	public DeviceSearchTargetController(DeviceSearchTargetService service) {
		this.service = service;
	}

	@GetMapping("/search-targets")
	@Transactional(readOnly = true)
	public ResponseEntity<ApiResponse<List<SearchTargetResponse>>> findTargets(
			@AuthenticationPrincipal MediaServerPrincipal principal,
			@RequestHeader(value = HttpHeaders.IF_NONE_MATCH, required = false) String ifNoneMatch) {
		String etag = buildEtag(principal, service.findLastModified(principal));
		CacheControl cacheControl = CacheControl.noCache().cachePrivate().mustRevalidate();
		if (matches(ifNoneMatch, etag)) {
			return ResponseEntity.status(HttpStatus.NOT_MODIFIED)
				.eTag(etag)
				.cacheControl(cacheControl)
				.build();
		}

		return ResponseEntity.ok()
				.eTag(etag)
				.cacheControl(cacheControl)
				.body(ApiResponse.of(service.findTargets(principal)));
	}

	private String buildEtag(MediaServerPrincipal principal, Instant lastModified) {
		String version = lastModified == null ? "empty" : lastModified.toString();
		return "\"media-server-" + principal.mediaServerId() + "-search-targets-" + version + "\"";
	}

	private boolean matches(String ifNoneMatch, String etag) {
		if (ifNoneMatch == null) return false;
		for (String candidate : ifNoneMatch.split(",")) {
			String normalized = candidate.trim();
			if ("*".equals(normalized) || etag.equals(normalized)) return true;
		}
		return false;
	}
}
