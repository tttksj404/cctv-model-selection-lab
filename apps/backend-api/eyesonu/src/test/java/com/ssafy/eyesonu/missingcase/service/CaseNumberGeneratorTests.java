package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.util.HashSet;
import java.util.Set;
import org.junit.jupiter.api.Test;

class CaseNumberGeneratorTests {

	private final CaseNumberGenerator generator = new CaseNumberGenerator();

	@Test
	void generates128BitCrockfordBase32CaseNumbers() {
		Set<String> generated = new HashSet<>();
		for (int index = 0; index < 1_000; index++) {
			String caseNumber = generator.generate();
			assertEquals(30, caseNumber.length());
			assertTrue(caseNumber.matches("EFU-[0-9A-HJKMNP-TV-Z]{26}"));
			assertTrue(generated.add(caseNumber));
		}
	}
}
