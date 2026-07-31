package com.ssafy.eyesonu.mediaserver.controller.admin;

import com.ssafy.eyesonu.common.api.ApiResponse;
import com.ssafy.eyesonu.mediaserver.controller.docs.AdminMediaServerControllerDocs;
import com.ssafy.eyesonu.mediaserver.dto.MediaServerOptionResponse;
import com.ssafy.eyesonu.mediaserver.service.MediaServerQueryService;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/api/v1/admin/media-servers")
public class AdminMediaServerController implements AdminMediaServerControllerDocs {

	private final MediaServerQueryService mediaServerQueryService;

	public AdminMediaServerController(MediaServerQueryService mediaServerQueryService) {
		this.mediaServerQueryService = mediaServerQueryService;
	}

	@GetMapping("/options")
	@Override
	public ResponseEntity<ApiResponse<List<MediaServerOptionResponse>>> findActiveOptions() {
		return ResponseEntity.ok(ApiResponse.of(mediaServerQueryService.findActiveOptions()));
	}
}
