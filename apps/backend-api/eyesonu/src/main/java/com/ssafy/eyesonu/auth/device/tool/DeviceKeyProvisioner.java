package com.ssafy.eyesonu.auth.device.tool;

import com.ssafy.eyesonu.auth.device.DeviceKey;
import java.security.SecureRandom;
import java.util.HexFormat;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;

public final class DeviceKeyProvisioner {

	private static final int KEY_ID_BYTES = 8;
	private static final int SECRET_BYTES = 32;
	private static final String BCRYPT_PREFIX = "{bcrypt}";

	private final SecureRandom secureRandom;
	private final BCryptPasswordEncoder passwordEncoder;

	public DeviceKeyProvisioner() {
		this(new SecureRandom(), new BCryptPasswordEncoder(12));
	}

	DeviceKeyProvisioner(SecureRandom secureRandom, BCryptPasswordEncoder passwordEncoder) {
		this.secureRandom = secureRandom;
		this.passwordEncoder = passwordEncoder;
	}

	public ProvisioningResult generate(String serverCode, String name) {
		byte[] keyIdBytes = new byte[KEY_ID_BYTES];
		byte[] secretBytes = new byte[SECRET_BYTES];
		secureRandom.nextBytes(keyIdBytes);
		secureRandom.nextBytes(secretBytes);

		String deviceKey = DeviceKey.PREFIX
				+ HexFormat.of().formatHex(keyIdBytes)
				+ "."
				+ HexFormat.of().formatHex(secretBytes);
		return importExisting(serverCode, name, deviceKey);
	}

	public ProvisioningResult importExisting(String serverCode, String name, String rawDeviceKey) {
		String normalizedServerCode = validateServerCode(serverCode);
		String normalizedName = validateName(name);
		DeviceKey deviceKey = DeviceKey.parse(rawDeviceKey)
				.orElseThrow(() -> new IllegalArgumentException(
						"Device Key must match msk_<16 lowercase hex>.<64 lowercase hex>"));
		String encodedSecret = BCRYPT_PREFIX + passwordEncoder.encode(deviceKey.secret());
		String sql = buildInsertSql(
				normalizedServerCode, normalizedName, deviceKey.keyId(), encodedSecret);
		return new ProvisioningResult(rawDeviceKey, deviceKey.keyId(), encodedSecret, sql);
	}

	private String validateServerCode(String value) {
		if (value == null || !value.matches("^[a-z0-9][a-z0-9-]{2,49}$")) {
			throw new IllegalArgumentException(
					"serverCode must be 3-50 lowercase letters, digits, or hyphens");
		}
		return value;
	}

	private String validateName(String value) {
		if (value == null) {
			throw new IllegalArgumentException("name is required");
		}
		String normalized = value.trim();
		if (normalized.isEmpty() || normalized.length() > 100 || normalized.chars().anyMatch(Character::isISOControl)) {
			throw new IllegalArgumentException("name must be 1-100 characters without control characters");
		}
		return normalized;
	}

	private String buildInsertSql(
			String serverCode, String name, String deviceKeyId, String deviceKeyHash) {
		return """
				INSERT INTO media_servers (server_code, name, device_key_id, device_key_hash, status)
				VALUES (%s, %s, %s, %s, 'ACTIVE');
				""".formatted(
					sqlLiteral(serverCode),
					sqlLiteral(name),
					sqlLiteral(deviceKeyId),
					sqlLiteral(deviceKeyHash));
	}

	private String sqlLiteral(String value) {
		return "'" + value.replace("'", "''") + "'";
	}

	public record ProvisioningResult(
			String deviceKey,
			String deviceKeyId,
			String deviceKeyHash,
			String insertSql) {

		@Override
		public String toString() {
			return "ProvisioningResult[deviceKey=<redacted>, deviceKeyId=" + deviceKeyId
					+ ", deviceKeyHash=<redacted>]";
		}
	}
}
