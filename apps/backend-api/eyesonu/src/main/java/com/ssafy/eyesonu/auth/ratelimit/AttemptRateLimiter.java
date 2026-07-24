package com.ssafy.eyesonu.auth.ratelimit;

import com.github.benmanes.caffeine.cache.Cache;
import com.github.benmanes.caffeine.cache.Caffeine;
import com.ssafy.eyesonu.auth.config.AuthProperties;
import java.nio.charset.StandardCharsets;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.time.Duration;
import java.util.HexFormat;
import java.util.concurrent.atomic.AtomicInteger;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

@Component
public class AttemptRateLimiter {

	private static final int COMPOSITE_LIMIT = 5;
	private static final int IP_LIMIT = 30;
	private static final Duration WINDOW = Duration.ofMinutes(10);

	private final byte[] hmacSecret;
	private final Cache<String, AtomicInteger> compositeFailures;
	private final Cache<String, AtomicInteger> ipFailures;
	private final Cache<String, Boolean> limitedAuditMarkers;

	public AttemptRateLimiter(AuthProperties properties) {
		if (!StringUtils.hasText(properties.getRateLimitKeySecret())) {
			throw new IllegalStateException("AUTH_RATE_LIMIT_KEY_SECRET must be configured");
		}
		this.hmacSecret = properties.getRateLimitKeySecret().getBytes(StandardCharsets.UTF_8);
		this.compositeFailures = newCache();
		this.ipFailures = newCache();
		this.limitedAuditMarkers = Caffeine.newBuilder().expireAfterWrite(WINDOW).build();
	}

	public boolean isAllowed(String scope, String ipAddress, String identifier) {
		Keys keys = keys(scope, ipAddress, identifier);
		return count(compositeFailures, keys.composite()) < COMPOSITE_LIMIT
				&& count(ipFailures, keys.ip()) < IP_LIMIT;
	}

	public void recordFailure(String scope, String ipAddress, String identifier) {
		Keys keys = keys(scope, ipAddress, identifier);
		increment(compositeFailures, keys.composite());
		increment(ipFailures, keys.ip());
	}

	public void recordSuccess(String scope, String ipAddress, String identifier) {
		compositeFailures.invalidate(keys(scope, ipAddress, identifier).composite());
	}

	public boolean shouldAuditLimited(String scope, String ipAddress, String identifier) {
		String key = keys(scope, ipAddress, identifier).composite();
		return limitedAuditMarkers.asMap().putIfAbsent(key, Boolean.TRUE) == null;
	}

	public String fingerprint(String value) {
		return hmac(value == null ? "" : value).substring(0, 16);
	}

	private Keys keys(String scope, String ipAddress, String identifier) {
		String normalizedIp = StringUtils.hasText(ipAddress) ? ipAddress : "unknown";
		return new Keys(
				hmac(scope + "|" + normalizedIp + "|" + identifier),
				hmac(scope + "|" + normalizedIp));
	}

	private Cache<String, AtomicInteger> newCache() {
		return Caffeine.newBuilder().expireAfterWrite(WINDOW).build();
	}

	private int count(Cache<String, AtomicInteger> cache, String key) {
		AtomicInteger value = cache.getIfPresent(key);
		return value == null ? 0 : value.get();
	}

	private void increment(Cache<String, AtomicInteger> cache, String key) {
		cache.get(key, ignored -> new AtomicInteger()).incrementAndGet();
	}

	private String hmac(String value) {
		try {
			Mac mac = Mac.getInstance("HmacSHA256");
			mac.init(new SecretKeySpec(hmacSecret, "HmacSHA256"));
			return HexFormat.of().formatHex(mac.doFinal(value.getBytes(StandardCharsets.UTF_8)));
		}
		catch (NoSuchAlgorithmException | InvalidKeyException exception) {
			throw new IllegalStateException("HmacSHA256 is unavailable", exception);
		}
	}

	private record Keys(String composite, String ip) {
	}
}
