package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import com.ssafy.eyesonu.common.exception.ApiException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

class CasePhotoValidatorTests {

	private CasePhotoValidator validator;

	@BeforeEach
	void setUp() {
		MinioProperties properties = new MinioProperties();
		properties.setCasePhotoMaxFileSizeBytes(10L * 1024 * 1024);
		validator = new CasePhotoValidator(properties);
	}

	@Test
	void acceptsMatchingJpegPngAndWebpSignatures() {
		assertEquals("jpg", validator.validate(file("image/jpeg", new byte[] {
				(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01})).extension());
		assertEquals("png", validator.validate(file("image/png", new byte[] {
				(byte) 0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a})).extension());
		assertEquals("webp", validator.validate(file("image/webp", new byte[] {
				'R', 'I', 'F', 'F', 0, 0, 0, 0, 'W', 'E', 'B', 'P'})).extension());
	}

	@Test
	void rejectsDeclaredTypeThatDoesNotMatchSignature() {
		ApiException exception = assertThrows(ApiException.class, () -> validator.validate(
				file("image/png", new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff})));
		assertEquals("UNSUPPORTED_MEDIA_TYPE", exception.getCode());
		assertEquals(415, exception.getStatus().value());
	}

	@Test
	void acceptsFileAtMaximumConfiguredSize() {
		MinioProperties properties = new MinioProperties();
		properties.setCasePhotoMaxFileSizeBytes(3);
		CasePhotoValidator exactLimit = new CasePhotoValidator(properties);

		CasePhotoValidator.ValidatedPhoto result = exactLimit.validate(
				file("image/jpg", new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff}));

		assertEquals("image/jpeg", result.contentType());
		assertEquals("jpg", result.extension());
	}

	@Test
	void rejectsMissingPhotoWithValidationError() {
		ApiException exception = assertThrows(ApiException.class, () -> validator.validate(null));

		assertEquals("VALIDATION_ERROR", exception.getCode());
		assertEquals(400, exception.getStatus().value());
	}

	@Test
	void rejectsOversizedFileBeforeReadingIt() {
		MinioProperties properties = new MinioProperties();
		properties.setCasePhotoMaxFileSizeBytes(2);
		CasePhotoValidator small = new CasePhotoValidator(properties);
		ApiException exception = assertThrows(ApiException.class, () -> small.validate(
				file("image/jpeg", new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff})));
		assertEquals("FILE_TOO_LARGE", exception.getCode());
		assertEquals(413, exception.getStatus().value());
	}

	private MockMultipartFile file(String type, byte[] bytes) {
		return new MockMultipartFile("photo", "photo", type, bytes);
	}
}
