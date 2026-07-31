package com.ssafy.eyesonu;

import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.boot.test.context.TestConfiguration;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Bean;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.utility.DockerImageName;

@TestConfiguration(proxyBeanMethods = false)
@ConditionalOnProperty(
		prefix = "testcontainers",
		name = "enabled",
		havingValue = "true",
		matchIfMissing = true)
public class TestDatabaseConfiguration {

	private static final MySQLContainer<?> MYSQL_CONTAINER = new MySQLContainer<>(
			DockerImageName.parse("mysql:8.0.46"))
			.withDatabaseName("eyesonu_test")
			.withUsername("eyesonu")
			.withPassword("eyesonu_test_password");

	@Bean(destroyMethod = "stop")
	@ServiceConnection
	MySQLContainer<?> mysqlContainer() {
		return MYSQL_CONTAINER;
	}
}
