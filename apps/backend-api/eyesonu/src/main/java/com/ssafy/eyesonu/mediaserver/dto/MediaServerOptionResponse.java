package com.ssafy.eyesonu.mediaserver.dto;

import com.ssafy.eyesonu.mediaserver.domain.MediaServerOption;
import io.swagger.v3.oas.annotations.media.Schema;

@Schema(description = "카메라 등록 화면에서 선택할 수 있는 활성 미디어 서버")
public record MediaServerOptionResponse(
		@Schema(description = "미디어 서버 ID", example = "1") Long id,
		@Schema(description = "미디어 서버 코드", example = "media-01") String serverCode,
		@Schema(description = "미디어 서버 이름", example = "서울 미디어 서버") String name) {

	public static MediaServerOptionResponse from(MediaServerOption option) {
		return new MediaServerOptionResponse(option.id(), option.serverCode(), option.name());
	}
}
