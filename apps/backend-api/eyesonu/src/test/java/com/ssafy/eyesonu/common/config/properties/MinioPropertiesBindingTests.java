package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.time.Duration;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

class MinioPropertiesBindingTests {

	@Test
	void bindsLocalMinioConfiguration() {
		Map<String, Object> values = Map.ofEntries(
				Map.entry("eyesonu.storage.minio.endpoint", "http://localhost:9000"),
				Map.entry("eyesonu.storage.minio.public-endpoint", "https://storage.example.test"),
				Map.entry("eyesonu.storage.minio.region", "ap-northeast-2"),
				Map.entry("eyesonu.storage.minio.bucket", "eyesonu-media"),
				Map.entry("eyesonu.storage.minio.access-key", "eyesonu-app"),
				Map.entry("eyesonu.storage.minio.secret-key", "eyesonu-app-secret"),
				Map.entry("eyesonu.storage.minio.connect-timeout", "2s"),
				Map.entry("eyesonu.storage.minio.read-timeout", "4s"),
				Map.entry("eyesonu.storage.minio.call-timeout", "8s"),
				Map.entry("eyesonu.storage.minio.max-file-size-bytes", "5368709120"),
				Map.entry("eyesonu.storage.minio.candidate-image-max-file-size-bytes", "8388608"),
				Map.entry("eyesonu.storage.minio.presigned-url-expiry", "10m"));

		MinioProperties properties = new Binder(new MapConfigurationPropertySource(values))
				.bind("eyesonu.storage.minio", Bindable.of(MinioProperties.class))
				.orElseThrow(() -> new AssertionError("MinIO properties were not bound"));

		assertEquals(URI.create("http://localhost:9000"), properties.getEndpoint());
		assertEquals(URI.create("https://storage.example.test"), properties.getPublicEndpoint());
		assertEquals("ap-northeast-2", properties.getRegion());
		assertEquals("eyesonu-media", properties.getBucket());
		assertEquals("eyesonu-app", properties.getAccessKey());
		assertEquals(Duration.ofSeconds(2), properties.getConnectTimeout());
		assertEquals(Duration.ofSeconds(4), properties.getReadTimeout());
		assertEquals(Duration.ofSeconds(8), properties.getCallTimeout());
		assertEquals(5_368_709_120L, properties.getMaxFileSizeBytes());
		assertEquals(8_388_608L, properties.getCandidateImageMaxFileSizeBytes());
		assertEquals(Duration.ofMinutes(10), properties.getPresignedUrlExpiry());
	}

}
