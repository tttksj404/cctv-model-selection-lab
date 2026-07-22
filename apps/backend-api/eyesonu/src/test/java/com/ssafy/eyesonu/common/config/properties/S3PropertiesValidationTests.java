package com.ssafy.eyesonu.common.config.properties;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

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

	private S3Properties validProperties() {
		S3Properties properties = new S3Properties();
		properties.setRegion("ap-northeast-2");
		properties.setBucket("eyesonu-media");
		return properties;
	}
}
