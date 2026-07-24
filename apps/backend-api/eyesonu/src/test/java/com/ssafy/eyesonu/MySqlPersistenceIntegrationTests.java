package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.caseinquiry.mapper.CaseInquiryMapper;
import java.time.LocalDateTime;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.testcontainers.containers.MySQLContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Testcontainers(disabledWithoutDocker = true)
class MySqlPersistenceIntegrationTests {

	@Container
	@ServiceConnection
	static final MySQLContainer<?> MYSQL = new MySQLContainer<>(
			DockerImageName.parse("mysql:8.0.46"))
			.withDatabaseName("eyesonu_test")
			.withUsername("eyesonu")
			.withPassword("eyesonu_test_password");

	@DynamicPropertySource
	static void properties(DynamicPropertyRegistry registry) {
		registry.add("spring.flyway.enabled", () -> true);
	}

	@Autowired
	private AdminMapper adminMapper;

	@Autowired
	private CaseInquiryMapper caseInquiryMapper;

	@Autowired
	private AuditLogMapper auditLogMapper;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Test
	void flywaySchemaAndAuthenticationMappersWorkAgainstMySql() {
		AdminInsertCommand command = new AdminInsertCommand(
				"admin", "{bcrypt}$2a$12$01234567890123456789012345678901234567890123456789012", "Admin");
		adminMapper.insert(command);
		assertTrue(command.getId() > 0);
		assertEquals("admin", adminMapper.findById(command.getId()).orElseThrow().loginId());

		jdbcTemplate.update(
				"INSERT INTO reporters (name, phone) VALUES (?, ?)", "Reporter", "01012345678");
		Long reporterId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM reporters", Long.class);
		jdbcTemplate.update("""
				INSERT INTO cases
				(reporter_id, case_number, status, report_content, missing_name, appearance,
				 last_seen_time, last_seen_address)
				VALUES (?, ?, 'SEARCHING', 'content', 'Missing', 'appearance', ?, 'address')
				""", reporterId, "EFU-0123456789ABCDEFGHJKMNPQRS", LocalDateTime.now());

		assertEquals(
				"SEARCHING",
				caseInquiryMapper.findStatus(
						"EFU-0123456789ABCDEFGHJKMNPQRS", "01012345678").orElseThrow().status());

		auditLogMapper.insert(command.getId(), null, "ADMIN_LOGIN_SUCCESS", "ADMIN", command.getId(), "{}");
		Integer auditCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_logs", Integer.class);
		assertEquals(1, auditCount);
	}
}
