package com.ssafy.eyesonu.storage;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.MinioClient;
import io.minio.StatObjectArgs;
import io.minio.errors.ErrorResponseException;

import org.springframework.stereotype.Component;

@Component
public class MinioStorageObjectVerifier implements StorageObjectVerifier {

	private final MinioClient client;
	private final S3Properties properties;

	public MinioStorageObjectVerifier(MinioClient client, S3Properties properties) {
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
		} catch (ErrorResponseException exception) {
			String errorCode = exception.errorResponse() == null ? null : exception.errorResponse().code();
			if ("NoSuchKey".equals(errorCode) || "NoSuchObject".equals(errorCode)) {
				throw new StorageObjectNotFoundException(exception);
			}
			throw new StorageObjectUnavailableException(exception);
		} catch (Exception exception) {
			throw new StorageObjectUnavailableException(exception);
		}
	}
}
