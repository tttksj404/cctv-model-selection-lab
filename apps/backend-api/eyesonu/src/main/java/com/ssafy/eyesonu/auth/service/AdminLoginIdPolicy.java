package com.ssafy.eyesonu.auth.service;

import java.util.Locale;
import java.util.regex.Pattern;

public final class AdminLoginIdPolicy {

	private static final Pattern PATTERN = Pattern.compile("[a-z0-9._-]{4,50}");

	private AdminLoginIdPolicy() {
	}

	public static String normalize(String loginId) {
		return loginId == null ? "" : loginId.trim().toLowerCase(Locale.ROOT);
	}

	public static boolean isValid(String loginId) {
		return PATTERN.matcher(loginId).matches();
	}
}
