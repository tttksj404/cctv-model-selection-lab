package com.ssafy.eyesonu.mediaserver.service;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.mediaserver.domain.MediaServerOption;
import com.ssafy.eyesonu.mediaserver.dto.MediaServerOptionResponse;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.util.List;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class MediaServerQueryServiceTests {

	private MediaServerMapper mediaServerMapper;
	private MediaServerQueryService service;

	@BeforeEach
	void setUp() {
		mediaServerMapper = mock(MediaServerMapper.class);
		service = new MediaServerQueryService(mediaServerMapper);
	}

	@Test
	void mapsSafeOptionsWithoutChangingMapperOrder() {
		when(mediaServerMapper.findActiveOptions()).thenReturn(List.of(
				new MediaServerOption(2L, "media-a", "Media Server A"),
				new MediaServerOption(7L, "media-z", "Media Server Z")));

		List<MediaServerOptionResponse> options = service.findActiveOptions();

		assertThat(options).containsExactly(
				new MediaServerOptionResponse(2L, "media-a", "Media Server A"),
				new MediaServerOptionResponse(7L, "media-z", "Media Server Z"));
		verify(mediaServerMapper).findActiveOptions();
	}

	@Test
	void returnsEmptyListWhenThereAreNoActiveServers() {
		when(mediaServerMapper.findActiveOptions()).thenReturn(List.of());

		assertThat(service.findActiveOptions()).isEmpty();
	}
}
