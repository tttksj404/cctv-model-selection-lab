package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;
import java.net.URI;

import jakarta.validation.Validation;
import jakarta.validation.Validator;

import org.junit.jupiter.api.Test;

class MinioPropertiesValidationTests {

	private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

	@Test
	void acceptsCompleteMinioConfiguration() {
		MinioProperties properties = validProperties();

		assertTrue(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsMissingBucketAndRegion() {
		MinioProperties properties = new MinioProperties();

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsMissingSecretKey() {
		MinioProperties properties = validProperties();
		properties.setSecretKey("");

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsNonPositiveTimeouts() {
		MinioProperties properties = validProperties();
		properties.setCallTimeout(Duration.ZERO);

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsInvalidPresignedUrlExpiry() {
		MinioProperties tooShort = validProperties();
		tooShort.setPresignedUrlExpiry(Duration.ofMillis(999));
		MinioProperties tooLong = validProperties();
		tooLong.setPresignedUrlExpiry(Duration.ofDays(7).plusSeconds(1));

		assertFalse(validator.validate(tooShort).isEmpty());
		assertFalse(validator.validate(tooLong).isEmpty());
	}

	@Test
	void rejectsNonPositiveMaxFileSize() {
		MinioProperties properties = validProperties();
		properties.setMaxFileSizeBytes(0);

		assertFalse(validator.validate(properties).isEmpty());
	}

	private MinioProperties validProperties() {
		MinioProperties properties = new MinioProperties();
		properties.setEndpoint(URI.create("http://minio:9000"));
		properties.setRegion("ap-northeast-2");
		properties.setBucket("eyesonu-media");
		properties.setPublicEndpoint(URI.create("https://storage.example.test"));
		properties.setAccessKey("eyesonu-app");
		properties.setSecretKey("eyesonu-app-secret");
		properties.setMaxFileSizeBytes(104_857_600L);
		return properties;
	}
}
