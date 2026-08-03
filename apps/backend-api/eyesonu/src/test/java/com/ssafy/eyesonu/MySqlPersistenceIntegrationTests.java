package com.ssafy.eyesonu;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

import com.ssafy.eyesonu.admin.mapper.AdminMapper;
import com.ssafy.eyesonu.admin.mapper.AdminMapper.AdminInsertCommand;
import com.ssafy.eyesonu.admin.domain.AdminRole;
import com.ssafy.eyesonu.audit.mapper.AuditLogMapper;
import com.ssafy.eyesonu.mediaserver.mapper.MediaServerMapper;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.CaseStatusInquiryRow;
import com.ssafy.eyesonu.missingcase.domain.CaseSortDirection;
import com.ssafy.eyesonu.missingcase.domain.CaseSortField;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.domain.ReporterRecord;
import com.ssafy.eyesonu.missingcase.mapper.CaseStatusInquiryMapper;
import com.ssafy.eyesonu.missingcase.mapper.MissingCaseMapper;
import java.time.Instant;
import java.time.LocalDateTime;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import org.springframework.context.annotation.Import;
import org.springframework.transaction.annotation.Transactional;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Import(TestDatabaseConfiguration.class)
@Transactional
class MySqlPersistenceIntegrationTests {

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
	private MissingCaseMapper missingCaseMapper;

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
		var storedAdmin = adminMapper.findById(command.getId()).orElseThrow();
		assertEquals("admin", storedAdmin.loginId());
		assertEquals(AdminRole.ADMIN, storedAdmin.role());
		assertTrue(storedAdmin.enabled());
		assertTrue(storedAdmin.createdAt() != null);

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
				(reporter_id, case_number, status, report_content, missing_name, gender,
				 distinctive_features,
				 last_seen_time, last_seen_address, reported_at, updated_at)
				VALUES (?, ?, 'SEARCHING', 'content', 'Missing', 'UNKNOWN', 'appearance', ?, 'address', ?, ?)
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

	@Test
	void adminManagedCaseSchemaAndMapperSupportCreateReadUpdateAndList() {
		ReporterRecord reporter = new ReporterRecord(
				null, "Reporter Two", "01099998888", "reporter2@example.com", "보호자");
		assertEquals(1, missingCaseMapper.insertReporter(reporter));

		MissingCaseRow row = new MissingCaseRow();
		row.setReporterId(reporter.getId());
		row.setCaseNumber("EFU-Z123456789ABCDEFGHJKMNPQRS");
		row.setStatus(CaseStatus.RECEIVED);
		row.setReportContent("content");
		row.setMissingName("Missing Two");
		row.setGender(Gender.UNKNOWN);
		row.setBirthYear(2000);
		row.setUpperClothing("black shirt");
		row.setLastSeenTime(Instant.parse("2026-07-20T00:00:00Z"));
		row.setLastSeenAddress("address");
		assertEquals(1, missingCaseMapper.insertCase(row));

		MissingCaseRow stored = missingCaseMapper.findById(row.getId());
		assertEquals("01099998888", stored.getReporterPhone());
		assertEquals("black shirt", stored.getUpperClothing());
		assertEquals(2000, stored.getBirthYear());

		stored.setReporterPhone("01011112222");
		stored.setBirthYear(null);
		stored.setUpperClothing("blue shirt");
		assertEquals(1, missingCaseMapper.updateReporter(stored));
		assertEquals(1, missingCaseMapper.updateCase(stored));
		assertEquals("01011112222", missingCaseMapper.findById(row.getId()).getReporterPhone());
		assertEquals(1L, missingCaseMapper.countCases(
				CaseStatus.RECEIVED, row.getCaseNumber(), "Missing", null, null));
		assertEquals(1, missingCaseMapper.findPage(
				CaseStatus.RECEIVED, row.getCaseNumber(), null, null, null,
				CaseSortField.REPORTED_AT, CaseSortDirection.DESC, 20, 0).size());

		assertEquals(0, jdbcTemplate.queryForObject("""
				SELECT COUNT(*) FROM information_schema.columns
				WHERE table_schema = DATABASE() AND table_name = 'cases'
				  AND column_name IN ('age_group', 'appearance')
				""", Integer.class));
	}

	@Test
	void adminManagedCaseDatabaseConstraintsRejectInvalidRequiredData() {
		jdbcTemplate.update(
				"INSERT INTO reporters (name, phone) VALUES (?, ?)", "Constraint Reporter", "01022223333");
		Long reporterId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM reporters", Long.class);
		String sql = """
				INSERT INTO cases
				(reporter_id, case_number, status, report_content, missing_name, gender,
				 birth_year, distinctive_features, last_seen_time,
				 last_seen_lat, last_seen_lng, last_seen_address)
				VALUES (?, ?, 'RECEIVED', ?, 'Missing', 'UNKNOWN', ?, ?, UTC_TIMESTAMP(6), ?, ?, 'address')
				""";

		assertThrows(DataAccessException.class, () -> jdbcTemplate.update(
				sql, reporterId, "EFU-Y123456789ABCDEFGHJKMNPQRS", "content", 1899, "coat", null, null));
		assertThrows(DataAccessException.class, () -> jdbcTemplate.update(
				sql, reporterId, "EFU-X123456789ABCDEFGHJKMNPQRS", "content", 2000, null, null, null));
		assertThrows(DataAccessException.class, () -> jdbcTemplate.update(
				sql, reporterId, "EFU-W123456789ABCDEFGHJKMNPQRS", "content", 2000, "coat", 37.5, null));
		assertThrows(DataAccessException.class, () -> jdbcTemplate.update(
				sql, reporterId, "EFU-V123456789ABCDEFGHJKMNPQRS", " ", 2000, "coat", null, null));
	}

	@Test
	void candidateSourceMigrationKeepsLegacyRealtimeInsertsCompatible() {
		jdbcTemplate.update(
				"INSERT INTO reporters (name, phone) VALUES ('Migration Reporter', '01033334444')");
		Long reporterId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM reporters", Long.class);
		jdbcTemplate.update("""
				INSERT INTO cases
				(reporter_id, case_number, status, report_content, missing_name, gender,
				 distinctive_features, last_seen_time, last_seen_address)
				VALUES (?, 'EFU-SOURCE-MIGRATION-000001', 'SEARCHING', 'content',
				        'Missing', 'UNKNOWN', 'coat', UTC_TIMESTAMP(6), 'address')
				""", reporterId);
		Long caseId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM cases", Long.class);
		jdbcTemplate.update("""
				INSERT INTO media_servers
				(server_code, name, device_key_id, device_key_hash, status)
				VALUES ('source-migration-server', 'Source Migration Server',
				        'sourcemigrate001', 'hash', 'ACTIVE')
				""");
		Long mediaServerId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM media_servers", Long.class);
		jdbcTemplate.update("""
				INSERT INTO cameras
				(media_server_id, camera_name, camera_code, latitude, longitude, address, stream_url)
				VALUES (?, 'Migration Camera', 'source-migration-camera', 37.5, 127.0,
				        'address', 'rtsp://source-migration')
				""", mediaServerId);
		Long cameraId = jdbcTemplate.queryForObject("SELECT MAX(id) FROM cameras", Long.class);

		jdbcTemplate.update("""
				INSERT INTO candidate_events
				(event_id, case_id, camera_id, detected_at, frame_object_key)
				VALUES ('legacy-event', ?, ?, UTC_TIMESTAMP(6), 'frames/legacy.jpg')
				""", caseId, cameraId);
		jdbcTemplate.update("""
				INSERT INTO candidates
				(case_id, camera_id, track_id, detected_time, first_detected_at, last_detected_at,
				 similarity, best_similarity, average_similarity, detection_count,
				 crop_object_key, frame_object_key, bounding_box, review_status, version)
				VALUES (?, ?, 'legacy-track', UTC_TIMESTAMP(6), UTC_TIMESTAMP(6), UTC_TIMESTAMP(6),
				        0.8, 0.8, 0.8, 1, 'crops/legacy.jpg', 'frames/legacy.jpg',
				        JSON_OBJECT('x', 1, 'y', 2, 'width', 30, 'height', 40), 'PENDING', 0)
				""", caseId, cameraId);

		assertEquals("REALTIME", jdbcTemplate.queryForObject(
				"SELECT source_type FROM candidates WHERE track_id = 'legacy-track'", String.class));
		assertEquals("realtime:" + caseId + ":" + cameraId, jdbcTemplate.queryForObject(
				"SELECT dedupe_scope FROM candidates WHERE track_id = 'legacy-track'", String.class));
		assertEquals("REALTIME", jdbcTemplate.queryForObject(
				"SELECT source_type FROM candidate_events WHERE event_id = 'legacy-event'", String.class));
	}
}
