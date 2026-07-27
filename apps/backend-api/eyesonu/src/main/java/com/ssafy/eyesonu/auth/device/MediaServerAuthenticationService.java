package com.ssafy.eyesonu.auth.device;

import com.ssafy.eyesonu.mediaserver.domain.MediaServer;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import java.util.Optional;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;

@Service
public class MediaServerAuthenticationService {

	private final MediaServerMapper mediaServerMapper;
	private final PasswordEncoder passwordEncoder;

	public MediaServerAuthenticationService(
			MediaServerMapper mediaServerMapper, PasswordEncoder passwordEncoder) {
		this.mediaServerMapper = mediaServerMapper;
		this.passwordEncoder = passwordEncoder;
	}

	public Optional<MediaServerPrincipal> authenticate(DeviceKey deviceKey) {
		return mediaServerMapper.findByDeviceKeyId(deviceKey.keyId())
				.filter(MediaServer::isActive)
				.filter(server -> passwordEncoder.matches(deviceKey.secret(), server.deviceKeyHash()))
				.map(server -> new MediaServerPrincipal(server.id(), server.serverCode()));
	}
}
