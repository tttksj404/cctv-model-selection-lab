package com.ssafy.eyesonu.missingcase.service;

import java.util.regex.Pattern;
import org.springframework.stereotype.Component;

@Component
public class PhoneNumberNormalizer {

	private static final Pattern ALLOWED_INPUT = Pattern.compile("[0-9 -]+");
	private static final Pattern NORMALIZED_PHONE = Pattern.compile("[0-9]{10,11}");

	public String normalize(String value) {
		if (value == null || !ALLOWED_INPUT.matcher(value).matches()) {
			throw new IllegalArgumentException("Phone number contains unsupported characters");
		}

		String normalized = value.replace("-", "").replace(" ", "");
		if (!NORMALIZED_PHONE.matcher(normalized).matches()) {
			throw new IllegalArgumentException("Phone number must contain 10 or 11 digits");
		}
		return normalized;
	}
}
