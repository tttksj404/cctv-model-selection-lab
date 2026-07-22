package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.util.Map;

import org.junit.jupiter.api.Test;
import org.springframework.boot.context.properties.bind.Bindable;
import org.springframework.boot.context.properties.bind.Binder;
import org.springframework.boot.context.properties.source.MapConfigurationPropertySource;

class S3PropertiesBindingTests {

	@Test
	void bindsLocalS3Configuration() {
		Map<String, Object> values = Map.of(
				"eyesonu.storage.s3.endpoint", "http://localhost:9000",
				"eyesonu.storage.s3.region", "ap-northeast-2",
				"eyesonu.storage.s3.bucket", "eyesonu-media",
				"eyesonu.storage.s3.path-style-access", "true",
				"eyesonu.storage.s3.access-key", "eyesonu-app",
				"eyesonu.storage.s3.secret-key", "eyesonu-app-secret");

		S3Properties properties = new Binder(new MapConfigurationPropertySource(values))
				.bind("eyesonu.storage.s3", Bindable.of(S3Properties.class))
				.orElseThrow(() -> new AssertionError("S3 properties were not bound"));

		assertEquals(URI.create("http://localhost:9000"), properties.getEndpoint());
		assertEquals("ap-northeast-2", properties.getRegion());
		assertEquals("eyesonu-media", properties.getBucket());
		assertTrue(properties.isPathStyleAccess());
		assertEquals("eyesonu-app", properties.getAccessKey());
	}

	@Test
	void bindsIamRoleConfigurationWithoutEndpointOrStaticCredentials() {
		Map<String, Object> values = Map.of(
				"eyesonu.storage.s3.endpoint", "",
				"eyesonu.storage.s3.region", "ap-northeast-2",
				"eyesonu.storage.s3.bucket", "eyesonu-prod",
				"eyesonu.storage.s3.path-style-access", "false",
				"eyesonu.storage.s3.access-key", "",
				"eyesonu.storage.s3.secret-key", "");

		S3Properties properties = new Binder(new MapConfigurationPropertySource(values))
				.bind("eyesonu.storage.s3", Bindable.of(S3Properties.class))
				.orElseThrow(() -> new AssertionError("S3 properties were not bound"));

		assertNull(properties.getEndpoint());
		assertFalse(properties.isPathStyleAccess());
		assertTrue(properties.isCredentialsComplete());
	}
}
