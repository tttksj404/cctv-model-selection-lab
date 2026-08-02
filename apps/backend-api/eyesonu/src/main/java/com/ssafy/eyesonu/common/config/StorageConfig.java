package com.ssafy.eyesonu.common.config;

import java.util.concurrent.TimeUnit;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.MinioClient;
import io.minio.credentials.AwsConfigProvider;
import io.minio.credentials.AwsEnvironmentProvider;
import io.minio.credentials.ChainedProvider;
import io.minio.credentials.IamAwsProvider;
import okhttp3.OkHttpClient;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.util.StringUtils;

@Configuration(proxyBeanMethods = false)
public class StorageConfig {

	@Bean
	public OkHttpClient storageHttpClient(S3Properties properties) {
		return new OkHttpClient.Builder()
				.connectTimeout(properties.getConnectTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.readTimeout(properties.getReadTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.callTimeout(properties.getCallTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.build();
	}

	@Bean
	public MinioClient minioClient(
			S3Properties properties,
			@Qualifier("storageHttpClient") OkHttpClient httpClient) {
		String endpoint = resolveInternalEndpoint(properties);
		return buildClient(endpoint, properties, httpClient);
	}

	@Bean
	public MinioClient publicMinioClient(
			S3Properties properties,
			@Qualifier("storageHttpClient") OkHttpClient httpClient) {
		return buildClient(properties.getPublicEndpoint().toString(), properties, httpClient);
	}

	private String resolveInternalEndpoint(S3Properties properties) {
		return properties.getEndpoint() == null
				? "https://s3.%s.amazonaws.com".formatted(properties.getRegion())
				: properties.getEndpoint().toString();
	}

	private MinioClient buildClient(String endpoint, S3Properties properties, OkHttpClient httpClient) {
		MinioClient.Builder builder = MinioClient.builder()
				.endpoint(endpoint)
				.region(properties.getRegion())
				.httpClient(httpClient, false);

		if (StringUtils.hasText(properties.getAccessKey())
				&& StringUtils.hasText(properties.getSecretKey())) {
			builder.credentials(properties.getAccessKey(), properties.getSecretKey());
		} else {
			builder.credentialsProvider(new ChainedProvider(
					new AwsEnvironmentProvider(),
					new AwsConfigProvider(null, null),
					new IamAwsProvider(null, httpClient)));
		}

		MinioClient client = builder.build();
		if (properties.isPathStyleAccess()) {
			client.disableVirtualStyleEndpoint();
		} else {
			client.enableVirtualStyleEndpoint();
		}
		return client;
	}
}
