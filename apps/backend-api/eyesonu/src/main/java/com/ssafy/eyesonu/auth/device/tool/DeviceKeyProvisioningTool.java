package com.ssafy.eyesonu.auth.device.tool;

import java.io.Console;
import java.util.Arrays;

public final class DeviceKeyProvisioningTool {

	private DeviceKeyProvisioningTool() {
	}

	public static void main(String[] args) {
		try {
			run(args);
		} catch (IllegalArgumentException exception) {
			System.err.println("ERROR: " + exception.getMessage());
			printUsage();
			System.exit(2);
		}
	}

	private static void run(String[] args) {
		if (args.length < 3) {
			throw new IllegalArgumentException("mode, serverCode, and name are required");
		}

		String mode = args[0];
		String serverCode = args[1];
		String name = String.join(" ", Arrays.copyOfRange(args, 2, args.length));
		DeviceKeyProvisioner provisioner = new DeviceKeyProvisioner();
		DeviceKeyProvisioner.ProvisioningResult result;

		if ("generate".equals(mode)) {
			result = provisioner.generate(serverCode, name);
		} else if ("import".equals(mode)) {
			Console console = System.console();
			if (console == null) {
				throw new IllegalArgumentException("import requires an interactive terminal");
			}
			char[] input = console.readPassword("Device Key: ");
			if (input == null || input.length == 0) {
				throw new IllegalArgumentException("Device Key is required");
			}
			try {
				result = provisioner.importExisting(serverCode, name, new String(input));
			} finally {
				Arrays.fill(input, '\0');
			}
		} else {
			throw new IllegalArgumentException("mode must be generate or import");
		}

		System.out.println("Store this Device Key now; it will not appear in the SQL below:");
		System.out.println(result.deviceKey());
		System.out.println();
		System.out.println("Run this SQL against the central database:");
		System.out.print(result.insertSql());
	}

	private static void printUsage() {
		System.err.println("Usage: DeviceKeyProvisioningTool <generate|import> <serverCode> <name>");
	}
}
