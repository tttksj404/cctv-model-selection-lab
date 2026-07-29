package com.ssafy.eyesonu.storage;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.time.Duration;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MinioClient;
import io.minio.StatObjectArgs;
import io.minio.StatObjectResponse;
import io.minio.errors.ErrorResponseException;
import io.minio.http.Method;
import io.minio.messages.ErrorResponse;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

class MinioStorageAdaptersTests {

	private static final String OBJECT_KEY = "recordings/CAM-001/private-video.mp4";

	private final MinioClient client = mock(MinioClient.class);
	private final S3Properties properties = properties();

	@Test
	void returnsObjectMetadataFromStat() throws Exception {
		StatObjectResponse response = mock(StatObjectResponse.class);
		when(response.size()).thenReturn(1024L);
		when(response.contentType()).thenReturn("video/mp4");
		when(client.statObject(any(StatObjectArgs.class))).thenReturn(response);

		StorageObject result = new MinioStorageObjectVerifier(client, properties).stat(OBJECT_KEY);

		assertEquals(new StorageObject(1024L, "video/mp4"), result);
	}

	@Test
	void mapsOnlyMissingObjectCodesToNotFound() throws Exception {
		ErrorResponseException noSuchObject = errorResponse("NoSuchObject");
		when(client.statObject(any(StatObjectArgs.class))).thenThrow(noSuchObject);

		RuntimeException result = assertThrows(
				StorageObjectNotFoundException.class,
				() -> new MinioStorageObjectVerifier(client, properties).stat(OBJECT_KEY));

		assertEquals("Storage object was not found", result.getMessage());
		assertTrue(!result.getMessage().contains(OBJECT_KEY));
	}

	@Test
	void mapsMissingBucketAndTransportFailuresToUnavailable() throws Exception {
		ErrorResponseException noSuchBucket = errorResponse("NoSuchBucket");
		when(client.statObject(any(StatObjectArgs.class))).thenThrow(noSuchBucket);

		RuntimeException missingBucket = assertThrows(
				StorageObjectUnavailableException.class,
				() -> new MinioStorageObjectVerifier(client, properties).stat(OBJECT_KEY));

		when(client.statObject(any(StatObjectArgs.class))).thenThrow(new IOException("timed out"));
		RuntimeException transportFailure = assertThrows(
				StorageObjectUnavailableException.class,
				() -> new MinioStorageObjectVerifier(client, properties).stat(OBJECT_KEY));
		assertEquals("Storage service is unavailable", missingBucket.getMessage());
		assertEquals("Storage service is unavailable", transportFailure.getMessage());
		assertTrue(!transportFailure.getMessage().contains(OBJECT_KEY));
	}

	@Test
	void createsFifteenMinuteGetUrl() throws Exception {
		when(client.getPresignedObjectUrl(any(GetPresignedObjectUrlArgs.class)))
				.thenReturn("https://media.example.test/signed");
		ArgumentCaptor<GetPresignedObjectUrlArgs> argsCaptor =
				ArgumentCaptor.forClass(GetPresignedObjectUrlArgs.class);

		String result = new MinioStorageObjectUrlSigner(client, properties).createGetUrl(OBJECT_KEY);

		verify(client).getPresignedObjectUrl(argsCaptor.capture());
		GetPresignedObjectUrlArgs args = argsCaptor.getValue();
		assertEquals("https://media.example.test/signed", result);
		assertEquals(Method.GET, args.method());
		assertEquals("eyesonu-media", args.bucket());
		assertEquals(OBJECT_KEY, args.object());
		assertEquals(900, args.expiry());
	}

	@Test
	void mapsSigningFailureToUnavailableWithoutLeakingKey() throws Exception {
		when(client.getPresignedObjectUrl(any(GetPresignedObjectUrlArgs.class)))
				.thenThrow(new IOException("could not sign"));

		RuntimeException result = assertThrows(
				StorageObjectUnavailableException.class,
				() -> new MinioStorageObjectUrlSigner(client, properties).createGetUrl(OBJECT_KEY));

		assertEquals("Storage service is unavailable", result.getMessage());
		assertInstanceOf(IOException.class, result.getCause());
		assertTrue(!result.getMessage().contains(OBJECT_KEY));
	}

	private ErrorResponseException errorResponse(String code) {
		ErrorResponseException exception = mock(ErrorResponseException.class);
		ErrorResponse response = mock(ErrorResponse.class);
		when(response.code()).thenReturn(code);
		when(exception.errorResponse()).thenReturn(response);
		return exception;
	}

	private S3Properties properties() {
		S3Properties properties = new S3Properties();
		properties.setRegion("ap-northeast-2");
		properties.setBucket("eyesonu-media");
		properties.setMaxFileSizeBytes(5_368_709_120L);
		properties.setPresignedUrlExpiry(Duration.ofMinutes(15));
		return properties;
	}
}
