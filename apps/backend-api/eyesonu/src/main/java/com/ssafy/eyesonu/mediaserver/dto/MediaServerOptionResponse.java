package com.ssafy.eyesonu.mediaserver.dto;

import com.ssafy.eyesonu.mediaserver.domain.MediaServerOption;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "카메라 등록 화면에서 선택할 수 있는 활성 Media Server")
public record MediaServerOptionResponse(
		@Schema(description = "Media Server ID", example = "1") Long id,
		@Schema(description = "Media Server 코드", example = "media-01") String serverCode,
		@Schema(description = "Media Server 이름", example = "서울 Media Server") String name) {

	public static MediaServerOptionResponse from(MediaServerOption option) {
		return new MediaServerOptionResponse(option.id(), option.serverCode(), option.name());
	}
}
