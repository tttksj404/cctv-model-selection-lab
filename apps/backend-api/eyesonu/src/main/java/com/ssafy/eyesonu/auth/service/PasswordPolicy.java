package com.ssafy.eyesonu.auth.service;

import com.ssafy.eyesonu.common.exception.ApiException;
import java.nio.charset.StandardCharsets;
import org.springframework.http.HttpStatus;

public final class PasswordPolicy {

	private PasswordPolicy() {
	}

	public static void validate(String password) {
		if (password == null
				|| password.length() < 12
				|| password.length() > 64
				|| password.getBytes(StandardCharsets.UTF_8).length > 72) {
			throw new ApiException(
					HttpStatus.BAD_REQUEST,
					"VALIDATION_ERROR",
					"비밀번호는 12~64자이며 UTF-8 기준 72바이트 이하여야 합니다.");
		}
	}
}
