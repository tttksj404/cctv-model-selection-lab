package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.time.Duration;

import jakarta.validation.Validation;
import jakarta.validation.Validator;

import org.junit.jupiter.api.Test;

class S3PropertiesValidationTests {

	private final Validator validator = Validation.buildDefaultValidatorFactory().getValidator();

	@Test
	void acceptsCompleteStaticCredentials() {
		S3Properties properties = validProperties();
		properties.setAccessKey("eyesonu-app");
		properties.setSecretKey("eyesonu-app-secret");

		assertTrue(validator.validate(properties).isEmpty());
	}

	@Test
	void acceptsOmittedCredentialsForIamRole() {
		assertTrue(validator.validate(validProperties()).isEmpty());
	}

	@Test
	void rejectsMissingBucketAndRegion() {
		S3Properties properties = new S3Properties();

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsOnlyOneCredential() {
		S3Properties properties = validProperties();
		properties.setAccessKey("eyesonu-app");

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsNonPositiveTimeouts() {
		S3Properties properties = validProperties();
		properties.setCallTimeout(Duration.ZERO);

		assertFalse(validator.validate(properties).isEmpty());
	}

	@Test
	void rejectsInvalidPresignedUrlExpiry() {
		S3Properties tooShort = validProperties();
		tooShort.setPresignedUrlExpiry(Duration.ofMillis(999));
		S3Properties tooLong = validProperties();
		tooLong.setPresignedUrlExpiry(Duration.ofDays(7).plusSeconds(1));

		assertFalse(validator.validate(tooShort).isEmpty());
		assertFalse(validator.validate(tooLong).isEmpty());
	}

	@Test
	void rejectsNonPositiveMaxFileSize() {
		S3Properties properties = validProperties();
		properties.setMaxFileSizeBytes(0);

		assertFalse(validator.validate(properties).isEmpty());
	}

	private S3Properties validProperties() {
		S3Properties properties = new S3Properties();
		properties.setRegion("ap-northeast-2");
		properties.setBucket("eyesonu-media");
		properties.setMaxFileSizeBytes(5_368_709_120L);
		return properties;
	}
}
