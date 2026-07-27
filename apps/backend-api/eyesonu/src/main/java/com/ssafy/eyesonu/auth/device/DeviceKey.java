package com.ssafy.eyesonu.auth.device;

import java.util.Optional;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class DeviceKey {

	public static final String PREFIX = "msk_";
	private static final Pattern FORMAT = Pattern.compile("^msk_([0-9a-f]{16})\\.([0-9a-f]{64})$");

	private final String keyId;
	private final char[] secret;

	private DeviceKey(String keyId, char[] secret) {
		this.keyId = keyId;
		this.secret = secret;
	}

	public static Optional<DeviceKey> parse(String value) {
		if (value == null) {
			return Optional.empty();
		}
		Matcher matcher = FORMAT.matcher(value);
		if (!matcher.matches()) {
			return Optional.empty();
		}
		return Optional.of(new DeviceKey(matcher.group(1), matcher.group(2).toCharArray()));
	}

	public String keyId() {
		return keyId;
	}

	public String secret() {
		return new String(secret);
	}

	@Override
	public String toString() {
		return PREFIX + keyId + ".<redacted>";
	}
}
