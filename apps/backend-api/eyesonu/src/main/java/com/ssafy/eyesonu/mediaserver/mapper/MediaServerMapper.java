package com.ssafy.eyesonu.mediaserver.mapper;

import com.ssafy.eyesonu.mediaserver.domain.MediaServer;
import java.util.Optional;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface MediaServerMapper {

	@Select("""
			SELECT id,
			       server_code AS serverCode,
			       name,
			       device_key_id AS deviceKeyId,
			       device_key_hash AS deviceKeyHash,
			       status
			FROM media_servers
			WHERE device_key_id = #{deviceKeyId}
			""")
	Optional<MediaServer> findByDeviceKeyId(String deviceKeyId);
}
