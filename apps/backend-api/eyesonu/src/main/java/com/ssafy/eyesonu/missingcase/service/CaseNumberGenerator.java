package com.ssafy.eyesonu.missingcase.service;

import java.math.BigInteger;
import java.security.SecureRandom;
import org.springframework.stereotype.Component;

@Component
public class CaseNumberGenerator {

	private static final char[] CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ".toCharArray();
	private static final int RANDOM_BYTES = 16;
	private static final int ENCODED_LENGTH = 26;

	private final SecureRandom secureRandom;

	public CaseNumberGenerator() {
		this(new SecureRandom());
	}

	CaseNumberGenerator(SecureRandom secureRandom) {
		this.secureRandom = secureRandom;
	}

	public String generate() {
		byte[] randomBytes = new byte[RANDOM_BYTES];
		secureRandom.nextBytes(randomBytes);
		BigInteger value = new BigInteger(1, randomBytes);
		char[] encoded = new char[ENCODED_LENGTH];
		for (int index = ENCODED_LENGTH - 1; index >= 0; index--) {
			BigInteger[] division = value.divideAndRemainder(BigInteger.valueOf(32));
			encoded[index] = CROCKFORD[division[1].intValue()];
			value = division[0];
		}
		return "EFU-" + new String(encoded);
	}
}
