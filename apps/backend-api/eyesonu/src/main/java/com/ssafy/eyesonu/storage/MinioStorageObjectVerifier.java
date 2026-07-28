package com.ssafy.eyesonu.storage;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.MinioClient;
import io.minio.StatObjectArgs;
import io.minio.errors.ErrorResponseException;
import io.minio.errors.MinioException;
import java.io.IOException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import org.springframework.stereotype.Component;

@Component
public class MinioStorageObjectVerifier implements StorageObjectVerifier {

    private final MinioClient client;
    private final S3Properties properties;

    public MinioStorageObjectVerifier(S3Properties properties) {
        this.properties = properties;
        MinioClient.Builder builder = MinioClient.builder()
                .endpoint(properties.getEndpoint().toString())
                .region(properties.getRegion());
        if (properties.getAccessKey() != null && properties.getSecretKey() != null) {
            builder.credentials(properties.getAccessKey(), properties.getSecretKey());
        }
        this.client = builder.build();
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
            if ("NoSuchKey".equals(exception.errorResponse().code())
                    || "NoSuchBucket".equals(exception.errorResponse().code())) {
                throw new StorageObjectNotFoundException(objectKey, exception);
            }
            throw new StorageObjectUnavailableException(objectKey, exception);
        } catch (MinioException | IOException | InvalidKeyException | NoSuchAlgorithmException exception) {
            throw new StorageObjectUnavailableException(objectKey, exception);
        }
    }
}
