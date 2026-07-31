package com.ssafy.eyesonu.mediaserver.mapper;

import static org.assertj.core.api.Assertions.assertThat;

import com.ssafy.eyesonu.mediaserver.domain.MediaServerOption;
import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@SpringBootTest(properties = "spring.flyway.enabled=true")
@ActiveProfiles("test")
@Testcontainers(disabledWithoutDocker = true)
@Transactional
@Sql(
		scripts = "/media-server-option-fixture.sql",
		config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.INFERRED))
class MediaServerMapperTests {

	@Container
	@ServiceConnection
	static final MySQLContainer<?> MYSQL = new MySQLContainer<>(
			DockerImageName.parse("mysql:8.0.46"))
			.withDatabaseName("eyesonu_media_server_test")
			.withUsername("eyesonu")
			.withPassword("eyesonu_test_password");

	@DynamicPropertySource
	static void properties(DynamicPropertyRegistry registry) {
		registry.add("spring.flyway.enabled", () -> true);
	}

	@Autowired
	private MediaServerMapper mediaServerMapper;

	@Test
	void activeOptionsSelectOnlySafeProjectionAndSortByServerCode() {
		List<MediaServerOption> options = mediaServerMapper.findActiveOptions();

		assertThat(options).containsExactly(
				new MediaServerOption(192002L, "option-a-server", "Option A Media Server"),
				new MediaServerOption(192001L, "option-z-server", "Option Z Media Server"));
	}
}
