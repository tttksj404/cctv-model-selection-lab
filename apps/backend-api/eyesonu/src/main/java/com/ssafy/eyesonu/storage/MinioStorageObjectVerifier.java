package com.ssafy.eyesonu.storage;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.MinioClient;
import io.minio.GetObjectArgs;
import io.minio.StatObjectArgs;
import io.minio.errors.ErrorResponseException;

import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.stereotype.Component;

@Component
public class MinioStorageObjectVerifier implements StorageObjectVerifier {

	private final MinioClient client;
	private final S3Properties properties;

	public MinioStorageObjectVerifier(
			@Qualifier("minioClient") MinioClient client,
			S3Properties properties) {
		this.client = client;
		this.properties = properties;
	}

	@Override
	public StorageObject stat(String objectKey) {
		try {
			var stat = client.statObject(StatObjectArgs.builder()
					.bucket(properties.getBucket())
					.object(objectKey)
					.build());
			return new StorageObject(stat.size(), stat.contentType());
		} catch (Exception exception) {
			throw mapException(exception);
		}
	}

	@Override
	public byte[] readPrefix(String objectKey, int length) {
		if (length <= 0) {
			throw new IllegalArgumentException("length must be greater than zero");
		}
		try (var response = client.getObject(GetObjectArgs.builder()
				.bucket(properties.getBucket())
				.object(objectKey)
				.offset(0L)
				.length((long) length)
				.build())) {
			return response.readNBytes(length);
		} catch (Exception exception) {
			throw mapException(exception);
		}
	}

	private RuntimeException mapException(Exception exception) {
		if (exception instanceof ErrorResponseException errorResponseException) {
			String errorCode = errorResponseException.errorResponse() == null
					? null : errorResponseException.errorResponse().code();
			if ("NoSuchKey".equals(errorCode) || "NoSuchObject".equals(errorCode)) {
				return new StorageObjectNotFoundException(exception);
			}
		}
		return new StorageObjectUnavailableException(exception);
	}
}
