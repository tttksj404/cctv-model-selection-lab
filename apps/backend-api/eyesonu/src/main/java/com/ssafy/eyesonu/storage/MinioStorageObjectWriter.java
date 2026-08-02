package com.ssafy.eyesonu.storage;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import java.io.ByteArrayInputStream;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

@Component
public class MinioStorageObjectWriter implements StorageObjectWriter {

	private final io.minio.MinioClient client;
	private final S3Properties properties;

	public MinioStorageObjectWriter(
			@Qualifier("minioClient") io.minio.MinioClient client,
			S3Properties properties) {
		this.client = client;
		this.properties = properties;
	}

	@Override
	public void put(String objectKey, byte[] content, String contentType) {
		try (ByteArrayInputStream input = new ByteArrayInputStream(content)) {
			client.putObject(PutObjectArgs.builder()
					.bucket(properties.getBucket())
					.object(objectKey)
					.stream(input, content.length, -1)
					.contentType(contentType)
					.build());
		}
		catch (Exception exception) {
			throw new StorageObjectUnavailableException(exception);
		}
	}

	@Override
	public void delete(String objectKey) {
		try {
			client.removeObject(RemoveObjectArgs.builder()
					.bucket(properties.getBucket())
					.object(objectKey)
					.build());
		}
		catch (Exception exception) {
			throw new StorageObjectUnavailableException(exception);
		}
	}
}
