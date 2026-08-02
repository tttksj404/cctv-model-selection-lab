package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.time.Duration;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

class S3PropertiesBindingTests {

	@Test
	void bindsLocalS3Configuration() {
		Map<String, Object> values = Map.ofEntries(
				Map.entry("eyesonu.storage.s3.endpoint", "http://localhost:9000"),
				Map.entry("eyesonu.storage.s3.public-endpoint", "https://storage.example.test"),
				Map.entry("eyesonu.storage.s3.region", "ap-northeast-2"),
				Map.entry("eyesonu.storage.s3.bucket", "eyesonu-media"),
				Map.entry("eyesonu.storage.s3.path-style-access", "true"),
				Map.entry("eyesonu.storage.s3.access-key", "eyesonu-app"),
				Map.entry("eyesonu.storage.s3.secret-key", "eyesonu-app-secret"),
				Map.entry("eyesonu.storage.s3.connect-timeout", "2s"),
				Map.entry("eyesonu.storage.s3.read-timeout", "4s"),
				Map.entry("eyesonu.storage.s3.call-timeout", "8s"),
				Map.entry("eyesonu.storage.s3.max-file-size-bytes", "5368709120"),
				Map.entry("eyesonu.storage.s3.presigned-url-expiry", "10m"));

		S3Properties properties = new Binder(new MapConfigurationPropertySource(values))
				.bind("eyesonu.storage.s3", Bindable.of(S3Properties.class))
				.orElseThrow(() -> new AssertionError("S3 properties were not bound"));

		assertEquals(URI.create("http://localhost:9000"), properties.getEndpoint());
		assertEquals(URI.create("https://storage.example.test"), properties.getPublicEndpoint());
		assertEquals("ap-northeast-2", properties.getRegion());
		assertEquals("eyesonu-media", properties.getBucket());
		assertTrue(properties.isPathStyleAccess());
		assertEquals("eyesonu-app", properties.getAccessKey());
		assertEquals(Duration.ofSeconds(2), properties.getConnectTimeout());
		assertEquals(Duration.ofSeconds(4), properties.getReadTimeout());
		assertEquals(Duration.ofSeconds(8), properties.getCallTimeout());
		assertEquals(5_368_709_120L, properties.getMaxFileSizeBytes());
		assertEquals(Duration.ofMinutes(10), properties.getPresignedUrlExpiry());
	}

	@Test
	void bindsIamRoleConfigurationWithoutEndpointOrStaticCredentials() {
		Map<String, Object> values = Map.of(
				"eyesonu.storage.s3.endpoint", "",
				"eyesonu.storage.s3.public-endpoint", "https://storage.example.test",
				"eyesonu.storage.s3.region", "ap-northeast-2",
				"eyesonu.storage.s3.bucket", "eyesonu-prod",
				"eyesonu.storage.s3.path-style-access", "false",
				"eyesonu.storage.s3.access-key", "",
				"eyesonu.storage.s3.secret-key", "",
				"eyesonu.storage.s3.max-file-size-bytes", "5368709120");

		S3Properties properties = new Binder(new MapConfigurationPropertySource(values))
				.bind("eyesonu.storage.s3", Bindable.of(S3Properties.class))
				.orElseThrow(() -> new AssertionError("S3 properties were not bound"));

		assertNull(properties.getEndpoint());
		assertFalse(properties.isPathStyleAccess());
		assertTrue(properties.isCredentialsComplete());
		assertEquals(Duration.ofSeconds(3), properties.getConnectTimeout());
		assertEquals(Duration.ofSeconds(5), properties.getReadTimeout());
		assertEquals(Duration.ofSeconds(10), properties.getCallTimeout());
		assertEquals(Duration.ofMinutes(15), properties.getPresignedUrlExpiry());
	}
}
