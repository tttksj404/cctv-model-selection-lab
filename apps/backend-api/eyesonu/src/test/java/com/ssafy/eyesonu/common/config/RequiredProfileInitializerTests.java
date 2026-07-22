package com.ssafy.eyesonu.common.config;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertThrows;

import org.junit.jupiter.api.Test;
import org.springframework.context.support.GenericApplicationContext;

class RequiredProfileInitializerTests {

	private final RequiredProfileInitializer initializer = new RequiredProfileInitializer();

	@Test
	void acceptsExactlyOneSupportedProfile() {
		try (GenericApplicationContext context = contextWithProfiles("local")) {
			assertDoesNotThrow(() -> initializer.initialize(context));
		}
	}

	@Test
	void rejectsMissingProfile() {
		try (GenericApplicationContext context = contextWithProfiles()) {
			assertThrows(IllegalStateException.class, () -> initializer.initialize(context));
		}
	}

	@Test
	void rejectsUnknownProfile() {
		try (GenericApplicationContext context = contextWithProfiles("development")) {
			assertThrows(IllegalStateException.class, () -> initializer.initialize(context));
		}
	}

	@Test
	void rejectsMultipleProfiles() {
		try (GenericApplicationContext context = contextWithProfiles("local", "prod")) {
			assertThrows(IllegalStateException.class, () -> initializer.initialize(context));
		}
	}

	private GenericApplicationContext contextWithProfiles(String... profiles) {
		GenericApplicationContext context = new GenericApplicationContext();
		context.getEnvironment().setActiveProfiles(profiles);
		return context;
	}
}
