package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import java.time.Instant;
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
	private CaseStatusInquiryMapper caseStatusInquiryMapper;

	@Autowired
	private AuditLogMapper auditLogMapper;

	@Autowired
	private MediaServerMapper mediaServerMapper;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Test
	void flywaySchemaAndAuthenticationMappersWorkAgainstMySql() {
		AdminInsertCommand command = new AdminInsertCommand(
				"admin", "{bcrypt}$2a$12$01234567890123456789012345678901234567890123456789012", "Admin");
		adminMapper.insert(command);
		assertTrue(command.getId() > 0);
		assertEquals("admin", adminMapper.findById(command.getId()).orElseThrow().loginId());

		jdbcTemplate.update("""
				INSERT INTO media_servers
				(server_code, name, device_key_id, device_key_hash, status)
				VALUES (?, ?, ?, ?, 'ACTIVE')
				""",
				"rpi5-media-01",
				"Raspberry Pi 5 Media Server",
				"0123456789abcdef",
				"{bcrypt}$2a$12$01234567890123456789012345678901234567890123456789012");
		Long mediaServerId = mediaServerMapper.findByDeviceKeyId("0123456789abcdef")
				.orElseThrow()
				.id();
		assertTrue(mediaServerId > 0);

		jdbcTemplate.update("""
				INSERT INTO cameras
				(media_server_id, camera_name, camera_code, latitude, longitude, address, stream_url)
				VALUES (?, 'Camera 01', 'camera-01', 37.5015, 127.0402, 'address', 'rtsp://camera/live')
				""", mediaServerId);
		assertEquals(
				0,
				jdbcTemplate.queryForObject("""
						SELECT COUNT(*)
						FROM information_schema.columns
						WHERE table_schema = DATABASE()
						  AND table_name = 'cameras'
						  AND column_name = 'device_key_hash'
						""", Integer.class));
		assertEquals(
				"NO",
				jdbcTemplate.queryForObject("""
						SELECT is_nullable
						FROM information_schema.columns
						WHERE table_schema = DATABASE()
						  AND table_name = 'cameras'
						  AND column_name = 'media_server_id'
						""", String.class));

		jdbcTemplate.update(
				"INSERT INTO reporters (name, phone) VALUES (?, ?)", "Reporter", "01012345678");
		Long reporterId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM reporters", Long.class);
		LocalDateTime reportedAt = LocalDateTime.of(2026, 7, 20, 1, 30, 15, 123_456_000);
		LocalDateTime updatedAt = LocalDateTime.of(2026, 7, 20, 2, 20, 25, 654_321_000);
		jdbcTemplate.update("""
				INSERT INTO cases
				(reporter_id, case_number, status, report_content, missing_name, appearance,
				 last_seen_time, last_seen_address, reported_at, updated_at)
				VALUES (?, ?, 'SEARCHING', 'content', 'Missing', 'appearance', ?, 'address', ?, ?)
				""",
				reporterId,
				"EFU-0123456789ABCDEFGHJKMNPQRS",
				reportedAt,
				reportedAt,
				updatedAt);

		CaseStatusInquiryRow inquiry = caseStatusInquiryMapper.findStatus(
				"EFU-0123456789ABCDEFGHJKMNPQRS", "01012345678").orElseThrow();
		assertEquals(CaseStatus.SEARCHING, inquiry.status());
		assertEquals(Instant.parse("2026-07-20T01:30:15.123456Z"), inquiry.reportedAt());
		assertEquals(Instant.parse("2026-07-20T02:20:25.654321Z"), inquiry.updatedAt());
		assertNull(inquiry.closedAt());

		auditLogMapper.insert(command.getId(), null, "ADMIN_LOGIN_SUCCESS", "ADMIN", command.getId(), "{}");
		Integer auditCount = jdbcTemplate.queryForObject("SELECT COUNT(*) FROM audit_logs", Integer.class);
		assertEquals(1, auditCount);
	}
}
