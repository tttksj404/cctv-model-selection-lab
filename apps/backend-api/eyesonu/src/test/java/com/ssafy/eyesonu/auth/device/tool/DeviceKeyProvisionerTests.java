package com.ssafy.eyesonu.auth.device.tool;

import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.auth.device.DeviceKey;
import org.junit.jupiter.api.Test;
import org.springframework.security.crypto.factory.PasswordEncoderFactories;
import org.springframework.security.crypto.password.PasswordEncoder;

class DeviceKeyProvisionerTests {

	private final DeviceKeyProvisioner provisioner = new DeviceKeyProvisioner();

	@Test
	void generatesExpectedFormatAndMatchingBcryptHash() {
		DeviceKeyProvisioner.ProvisioningResult result =
				provisioner.generate("rpi5-media-01", "Raspberry Pi 5 Media Server");
		DeviceKey parsed = DeviceKey.parse(result.deviceKey()).orElseThrow();
		PasswordEncoder passwordEncoder = PasswordEncoderFactories.createDelegatingPasswordEncoder();

		assertTrue(result.deviceKey().matches("^msk_[0-9a-f]{16}\\.[0-9a-f]{64}$"));
		assertTrue(passwordEncoder.matches(parsed.secret(), result.deviceKeyHash()));
		assertTrue(result.insertSql().contains(result.deviceKeyId()));
		assertFalse(result.insertSql().contains(result.deviceKey()));
		assertFalse(result.insertSql().contains(parsed.secret()));
		assertFalse(result.toString().contains(parsed.secret()));
	}

	@Test
	void importsExistingKeyAndRejectsInvalidInputs() {
		String deviceKey = "msk_0123456789abcdef."
				+ "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef";

		DeviceKeyProvisioner.ProvisioningResult result =
				provisioner.importExisting("rpi5-media-01", "Media Server", deviceKey);

		assertTrue(result.insertSql().contains("'0123456789abcdef'"));
		assertThrows(
				IllegalArgumentException.class,
				() -> provisioner.importExisting("RPI 5", "Media Server", deviceKey));
		assertThrows(
				IllegalArgumentException.class,
				() -> provisioner.importExisting("rpi5-media-01", "Media Server", "invalid"));
	}
}
