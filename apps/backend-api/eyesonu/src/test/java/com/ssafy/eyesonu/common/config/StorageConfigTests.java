package com.ssafy.eyesonu.common.config;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import java.net.URI;
import java.time.Duration;

import com.ssafy.eyesonu.common.config.properties.S3Properties;
import io.minio.GetPresignedObjectUrlArgs;
import io.minio.MinioClient;
import io.minio.http.Method;
import okhttp3.OkHttpClient;
import org.junit.jupiter.api.Test;

class StorageConfigTests {

	private final StorageConfig config = new StorageConfig();

	@Test
	void configuresSharedHttpClientTimeouts() {
		S3Properties properties = properties();
		properties.setConnectTimeout(Duration.ofSeconds(2));
		properties.setReadTimeout(Duration.ofSeconds(4));
		properties.setCallTimeout(Duration.ofSeconds(8));

		OkHttpClient client = config.storageHttpClient(properties);

		assertEquals(2_000, client.connectTimeoutMillis());
		assertEquals(4_000, client.readTimeoutMillis());
		assertEquals(8_000, client.callTimeoutMillis());
	}

	@Test
	void buildsIamClientWithoutEndpointOrStaticCredentials() {
		S3Properties properties = properties();
		properties.setEndpoint(null);
		properties.setAccessKey(" ");
		properties.setSecretKey("");
		properties.setPathStyleAccess(false);
		OkHttpClient httpClient = config.storageHttpClient(properties);

		MinioClient client = config.minioClient(properties, httpClient);

		assertNotNull(client);
	}

	@Test
	void createsPathStyleClientWithStaticCredentials() throws Exception {
		S3Properties properties = properties();
		properties.setEndpoint(URI.create("http://storage.example.test:9000"));
		properties.setAccessKey("access-key");
		properties.setSecretKey("secret-key");
		properties.setPathStyleAccess(true);
		MinioClient client = config.minioClient(properties, config.storageHttpClient(properties));

		String url = client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
				.method(Method.GET)
				.bucket(properties.getBucket())
				.object("recordings/CAM-001/video.mp4")
				.expiry(15 * 60)
				.build());

		assertTrue(url.startsWith("http://storage.example.test:9000/eyesonu-media/"));
	}

	@Test
	void createsPresignedUrlsWithPublicEndpoint() throws Exception {
		S3Properties properties = properties();
		properties.setEndpoint(URI.create("http://minio:9000"));
		properties.setPublicEndpoint(URI.create("https://storage.example.test"));
		properties.setAccessKey("access-key");
		properties.setSecretKey("secret-key");
		properties.setPathStyleAccess(true);

		MinioClient client = config.publicMinioClient(properties, config.storageHttpClient(properties));
		String url = client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
				.method(Method.GET)
				.bucket(properties.getBucket())
				.object("recordings/CAM-001/video.mp4")
				.expiry(15 * 60)
				.build());

		assertTrue(url.startsWith("https://storage.example.test/eyesonu-media/"));
		assertTrue(!url.contains("minio:9000"));
	}

	@Test
	void createsRegionalVirtualStyleClientWhenEndpointIsOmitted() throws Exception {
		S3Properties properties = properties();
		properties.setEndpoint(null);
		properties.setAccessKey("access-key");
		properties.setSecretKey("secret-key");
		properties.setPathStyleAccess(false);
		MinioClient client = config.minioClient(properties, config.storageHttpClient(properties));

		String url = client.getPresignedObjectUrl(GetPresignedObjectUrlArgs.builder()
				.method(Method.GET)
				.bucket(properties.getBucket())
				.object("recordings/CAM-001/video.mp4")
				.expiry(15 * 60)
				.build());

		assertTrue(url.startsWith(
				"https://eyesonu-media.s3.ap-northeast-2.amazonaws.com/recordings/CAM-001/video.mp4"));
	}

	private S3Properties properties() {
		S3Properties properties = new S3Properties();
		properties.setRegion("ap-northeast-2");
		properties.setBucket("eyesonu-media");
		properties.setPublicEndpoint(URI.create("http://localhost:9000"));
		properties.setMaxFileSizeBytes(5_368_709_120L);
		return properties;
	}
}
