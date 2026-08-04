package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import org.junit.jupiter.api.Test;

class RealtimePromptNormalizerTests {

	private final RealtimePromptNormalizer normalizer = new RealtimePromptNormalizer();

	@Test
	void normalizesSupportedKoreanDescriptionToCanonicalPrompt() {
		assertEquals(
				"a woman wearing a red short sleeve top and black pants",
				normalizer.normalize("여성, 빨간색 반팔 상의와 검은색 하의"));
	}

	@Test
	void canonicalPromptRemainsCanonical() {
		String prompt = "a person wearing a blue long sleeve top and white pants";

		assertEquals(prompt, normalizer.normalize(prompt));
		assertTrue(normalizer.isUsable(prompt, null));
	}

	@Test
	void rejectsPromptOrExclusionThatCannotBeNormalized() {
		String validPrompt = "a man wearing a green short sleeve top and brown pants";

		assertNull(normalizer.normalizeOrNull("person in a green shirt"));
		assertFalse(normalizer.isUsable("person in a green shirt", null));
		assertFalse(normalizer.isUsable(validPrompt, "person in a red shirt"));
	}
}
