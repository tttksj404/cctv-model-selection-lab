package com.ssafy.eyesonu.auth.ratelimit;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.auth.config.AuthProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

class AttemptRateLimiterTests {

	private AttemptRateLimiter rateLimiter;

	@BeforeEach
	void setUp() {
		AuthProperties properties = new AuthProperties();
		properties.setRateLimitKeySecret("unit-test-rate-limit-secret");
		rateLimiter = new AttemptRateLimiter(properties);
	}

	@Test
	void permitsFiveFailuresAndRejectsTheSixthAttempt() {
		for (int attempt = 0; attempt < 5; attempt++) {
			assertTrue(rateLimiter.isAllowed("login", "127.0.0.1", "admin"));
			rateLimiter.recordFailure("login", "127.0.0.1", "admin");
		}
		assertFalse(rateLimiter.isAllowed("login", "127.0.0.1", "admin"));
	}

	@Test
	void successClearsOnlyTheCompositeFailureCounter() {
		for (int attempt = 0; attempt < 5; attempt++) {
			rateLimiter.recordFailure("login", "127.0.0.1", "admin");
		}
		rateLimiter.recordSuccess("login", "127.0.0.1", "admin");
		assertTrue(rateLimiter.isAllowed("login", "127.0.0.1", "admin"));
	}

	@Test
	void onlyFirstLimitedAttemptInAWindowIsMarkedForAudit() {
		assertTrue(rateLimiter.shouldAuditLimited("login", "127.0.0.1", "admin"));
		assertFalse(rateLimiter.shouldAuditLimited("login", "127.0.0.1", "admin"));
	}
}
