package com.ssafy.eyesonu.common.config.properties;

import java.net.URI;
import java.time.Duration;

import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import jakarta.validation.constraints.Positive;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.util.StringUtils;
import org.springframework.validation.annotation.Validated;

@Validated
@ConfigurationProperties(prefix = "eyesonu.storage.s3")
public class S3Properties {

	private static final Duration MAX_PRESIGNED_URL_EXPIRY = Duration.ofDays(7);

	private URI endpoint;

	@NotNull
	private URI publicEndpoint;

	@NotBlank
	private String region;

	@NotBlank
	private String bucket;

	private boolean pathStyleAccess;

	private String accessKey;

	private String secretKey;

	@NotNull
	private Duration connectTimeout = Duration.ofSeconds(3);

	@NotNull
	private Duration readTimeout = Duration.ofSeconds(5);

	@NotNull
	private Duration callTimeout = Duration.ofSeconds(10);

	@Positive
	private long maxFileSizeBytes;

	@Positive
	private long casePhotoMaxFileSizeBytes = 10L * 1024 * 1024;

	@NotNull
	private Duration presignedUrlExpiry = Duration.ofMinutes(15);

	public URI getEndpoint() {
		return endpoint;
	}

	public void setEndpoint(URI endpoint) {
		this.endpoint = endpoint;
	}

	public URI getPublicEndpoint() {
		return publicEndpoint;
	}

	public void setPublicEndpoint(URI publicEndpoint) {
		this.publicEndpoint = publicEndpoint;
	}

	public String getRegion() {
		return region;
	}

	public void setRegion(String region) {
		this.region = region;
	}

	public String getBucket() {
		return bucket;
	}

	public void setBucket(String bucket) {
		this.bucket = bucket;
	}

	public boolean isPathStyleAccess() {
		return pathStyleAccess;
	}

	public void setPathStyleAccess(boolean pathStyleAccess) {
		this.pathStyleAccess = pathStyleAccess;
	}

	public String getAccessKey() {
		return accessKey;
	}

	public void setAccessKey(String accessKey) {
		this.accessKey = accessKey;
	}

	public String getSecretKey() {
		return secretKey;
	}

	public void setSecretKey(String secretKey) {
		this.secretKey = secretKey;
	}

	public Duration getConnectTimeout() {
		return connectTimeout;
	}

	public void setConnectTimeout(Duration connectTimeout) {
		this.connectTimeout = connectTimeout;
	}

	public Duration getReadTimeout() {
		return readTimeout;
	}

	public void setReadTimeout(Duration readTimeout) {
		this.readTimeout = readTimeout;
	}

	public Duration getCallTimeout() {
		return callTimeout;
	}

	public void setCallTimeout(Duration callTimeout) {
		this.callTimeout = callTimeout;
	}

	public long getMaxFileSizeBytes() {
		return maxFileSizeBytes;
	}

	public void setMaxFileSizeBytes(long maxFileSizeBytes) {
		this.maxFileSizeBytes = maxFileSizeBytes;
	}

	public long getCasePhotoMaxFileSizeBytes() {
		return casePhotoMaxFileSizeBytes;
	}

	public void setCasePhotoMaxFileSizeBytes(long casePhotoMaxFileSizeBytes) {
		this.casePhotoMaxFileSizeBytes = casePhotoMaxFileSizeBytes;
	}

	public Duration getPresignedUrlExpiry() {
		return presignedUrlExpiry;
	}

	public void setPresignedUrlExpiry(Duration presignedUrlExpiry) {
		this.presignedUrlExpiry = presignedUrlExpiry;
	}

	@AssertTrue(message = "S3 access-key and secret-key must either both be set or both be omitted")
	public boolean isCredentialsComplete() {
		return StringUtils.hasText(accessKey) == StringUtils.hasText(secretKey);
	}

	@AssertTrue(message = "S3 client timeouts must be greater than zero")
	public boolean isTimeoutsPositive() {
		return isPositive(connectTimeout) && isPositive(readTimeout) && isPositive(callTimeout);
	}

	@AssertTrue(message = "S3 presigned URL expiry must be between 1 second and 7 days")
	public boolean isPresignedUrlExpiryValid() {
		return presignedUrlExpiry != null
				&& presignedUrlExpiry.compareTo(Duration.ofSeconds(1)) >= 0
				&& presignedUrlExpiry.compareTo(MAX_PRESIGNED_URL_EXPIRY) <= 0;
	}

	private boolean isPositive(Duration duration) {
		return duration != null && !duration.isZero() && !duration.isNegative();
	}
}
