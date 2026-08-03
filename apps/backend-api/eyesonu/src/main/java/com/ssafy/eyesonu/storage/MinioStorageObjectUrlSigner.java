package com.ssafy.eyesonu.storage;

import java.util.concurrent.TimeUnit;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MinioClient;
import io.minio.http.Method;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

@Component
public class MinioStorageObjectUrlSigner implements StorageObjectUrlSigner {

	private final MinioClient client;
	private final S3Properties properties;

	public MinioStorageObjectUrlSigner(
			@Qualifier("publicMinioClient") MinioClient client,
			S3Properties properties) {
		this.client = client;
		this.properties = properties;
	}

	@Override
	public String createGetUrl(String objectKey) {
		try {
			int expirySeconds = Math.toIntExact(properties.getPresignedUrlExpiry().toSeconds());
			return client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
					.method(Method.GET)
					.bucket(properties.getBucket())
					.object(objectKey)
					.expiry(expirySeconds, TimeUnit.SECONDS)
					.build());
		} catch (Exception exception) {
			throw new StorageObjectUnavailableException(exception);
		}
	}
}
