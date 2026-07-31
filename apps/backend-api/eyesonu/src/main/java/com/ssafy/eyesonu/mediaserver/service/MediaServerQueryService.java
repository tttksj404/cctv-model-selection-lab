package com.ssafy.eyesonu.mediaserver.service;

import com.ssafy.eyesonu.mediaserver.dto.MediaServerOptionResponse;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.util.List;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Service
public class MediaServerQueryService {

	private final MediaServerMapper mediaServerMapper;

	public MediaServerQueryService(MediaServerMapper mediaServerMapper) {
		this.mediaServerMapper = mediaServerMapper;
	}

	@Transactional(readOnly = true)
	public List<MediaServerOptionResponse> findActiveOptions() {
		return mediaServerMapper.findActiveOptions().stream()
				.map(MediaServerOptionResponse::from)
				.toList();
	}
}
