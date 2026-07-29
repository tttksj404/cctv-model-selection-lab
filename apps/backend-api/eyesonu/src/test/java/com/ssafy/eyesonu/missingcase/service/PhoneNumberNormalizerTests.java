package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;

class PhoneNumberNormalizerTests {

	private final PhoneNumberNormalizer normalizer = new PhoneNumberNormalizer();

	@ParameterizedTest
	@ValueSource(strings = {
			"01012345678",
			"010-1234-5678",
			"010 1234 5678",
			"010 - 1234 - 5678"
	})
	void normalizesDigitsHyphensAndSpaces(String phone) {
		assertEquals("01012345678", normalizer.normalize(phone));
	}

	@Test
	void acceptsTenDigitPhoneNumber() {
		assertEquals("0212345678", normalizer.normalize("02-1234-5678"));
	}

	@Test
	void rejectsNullAndBlankInput() {
		assertThrows(IllegalArgumentException.class, () -> normalizer.normalize(null));
		assertThrows(IllegalArgumentException.class, () -> normalizer.normalize(""));
		assertThrows(IllegalArgumentException.class, () -> normalizer.normalize("   "));
	}

	@ParameterizedTest
	@ValueSource(strings = {
			"abc010-1234-5678",
			"010 (1234) 5678",
			"+82 10-1234-5678",
			"010.1234.5678",
			"010_1234_5678"
	})
	void rejectsCharactersOtherThanDigitsHyphensAndSpaces(String phone) {
		assertThrows(IllegalArgumentException.class, () -> normalizer.normalize(phone));
	}

	@ParameterizedTest
	@ValueSource(strings = {"123456789", "123456789012"})
	void rejectsNormalizedLengthsOutsideTenOrElevenDigits(String phone) {
		assertThrows(IllegalArgumentException.class, () -> normalizer.normalize(phone));
	}
}
