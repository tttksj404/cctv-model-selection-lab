package com.ssafy.eyesonu.common.config;

import java.util.Arrays;
import java.util.Set;

import org.springframework.context.ApplicationContextInitializer;
import org.springframework.context.ConfigurableApplicationContext;

public final class RequiredProfileInitializer
		implements ApplicationContextInitializer<ConfigurableApplicationContext> {

	private static final Set<String> SUPPORTED_PROFILES = Set.of("local", "test", "prod");

	@Override
	public void initialize(ConfigurableApplicationContext applicationContext) {
		Set<String> activeProfiles = Set.copyOf(
				Arrays.asList(applicationContext.getEnvironment().getActiveProfiles()));

		if (activeProfiles.size() != 1 || !SUPPORTED_PROFILES.containsAll(activeProfiles)) {
			throw new IllegalStateException(
					"Exactly one Spring profile must be active: local, test, or prod. Active profiles: "
							+ activeProfiles);
		}
	}
}
