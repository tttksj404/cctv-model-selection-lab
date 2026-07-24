package com.ssafy.eyesonu.auth.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "eyesonu.auth")
public class AuthProperties {

	private String rateLimitKeySecret;
	private final Bootstrap bootstrap = new Bootstrap();

	public String getRateLimitKeySecret() {
		return rateLimitKeySecret;
	}

	public void setRateLimitKeySecret(String rateLimitKeySecret) {
		this.rateLimitKeySecret = rateLimitKeySecret;
	}

	public Bootstrap getBootstrap() {
		return bootstrap;
	}

	public static class Bootstrap {

		private boolean enabled;
		private String loginId;
		private String password;
		private String name;

		public boolean isEnabled() {
			return enabled;
		}

		public void setEnabled(boolean enabled) {
			this.enabled = enabled;
		}

		public String getLoginId() {
			return loginId;
		}

		public void setLoginId(String loginId) {
			this.loginId = loginId;
		}

		public String getPassword() {
			return password;
		}

		public void setPassword(String password) {
			this.password = password;
		}

		public String getName() {
			return name;
		}

		public void setName(String name) {
			this.name = name;
		}
	}
}
