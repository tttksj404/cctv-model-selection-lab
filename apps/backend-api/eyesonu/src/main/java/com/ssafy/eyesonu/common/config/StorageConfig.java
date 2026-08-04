package com.ssafy.eyesonu.common.config;

import java.util.concurrent.TimeUnit;

import com.ssafy.eyesonu.common.config.properties.MinioProperties;
import io.minio.MinioClient;
import okhttp3.OkHttpClient;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration(proxyBeanMethods = false)
public class StorageConfig {

	@Bean
	public OkHttpClient storageHttpClient(MinioProperties properties) {
		return new OkHttpClient.Builder()
				.connectTimeout(properties.getConnectTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.readTimeout(properties.getReadTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.callTimeout(properties.getCallTimeout().toMillis(), TimeUnit.MILLISECONDS)
				.build();
	}

	@Bean
	public MinioClient minioClient(
			MinioProperties properties,
			@Qualifier("storageHttpClient") OkHttpClient httpClient) {
		return buildClient(properties.getEndpoint().toString(), properties, httpClient);
	}

	@Bean
	public MinioClient publicMinioClient(
			MinioProperties properties,
			@Qualifier("storageHttpClient") OkHttpClient httpClient) {
		return buildClient(properties.getPublicEndpoint().toString(), properties, httpClient);
	}

	private MinioClient buildClient(String endpoint, MinioProperties properties, OkHttpClient httpClient) {
		MinioClient.Builder builder = MinioClient.builder()
				.endpoint(endpoint)
				.region(properties.getRegion())
				.httpClient(httpClient, false)
				.credentials(properties.getAccessKey(), properties.getSecretKey());

		MinioClient client = builder.build();
		client.disableVirtualStyleEndpoint();
		return client;
	}
}
