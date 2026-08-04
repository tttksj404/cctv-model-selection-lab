package com.ssafy.eyesonu.missingcase.mapper;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertNull;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.missingcase.domain.DeviceSearchTargetRow;
import com.ssafy.eyesonu.missingcase.domain.SearchConditionRow;
import java.math.BigDecimal;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.testcontainers.service.connection.ServiceConnection;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;

@ActiveProfiles("test")
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS)
@Import(TestDatabaseConfiguration.class)
class DeviceSearchTargetMapperIntegrationTests {

	private static final long MEDIA_SERVER_ID = 178001L;
	private static final long CAMERA_ID = 178002L;
	private static final long REPORTER_ID = 178003L;
	private static final long CASE_ID = 178004L;
	private static final String CASE_NUMBER = "EFU-178-SEARCH-TARGET-TEST";

	@DynamicPropertySource
	static void properties(DynamicPropertyRegistry registry) {
		registry.add("spring.flyway.enabled", () -> true);
	}

	@Autowired
	private MissingCaseMapper mapper;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@BeforeEach
	void setUp() {
		cleanup();
		jdbcTemplate.update("""
				INSERT INTO media_servers
				(id, server_code, name, device_key_id, device_key_hash, status)
				VALUES (?, 'MS-178-TEST', 'Search Target Test Server', '1780012345678901', 'hash', 'ACTIVE')
				""", MEDIA_SERVER_ID);
		jdbcTemplate.update("""
				INSERT INTO cameras
				(id, media_server_id, camera_name, camera_code, latitude, longitude, address, stream_url)
				VALUES (?, ?, 'Search Target Camera', 'CAM-178-TEST', 37.5, 127.0, 'address', 'rtsp://camera/live')
				""", CAMERA_ID, MEDIA_SERVER_ID);
		jdbcTemplate.update("""
				INSERT INTO reporters (id, name, phone)
				VALUES (?, 'Search Target Reporter', '01017800001')
				""", REPORTER_ID);
		jdbcTemplate.update("""
				INSERT INTO cases
				(id, reporter_id, case_number, status, report_content, missing_name, gender,
				 distinctive_features, last_seen_time, last_seen_address, updated_at)
				VALUES (?, ?, ?, 'SEARCHING', 'content', 'Missing', 'UNKNOWN',
				        'appearance', ?, 'address', ?)
				""", CASE_ID, REPORTER_ID, CASE_NUMBER,
				LocalDateTime.of(2026, 7, 30, 0, 0), LocalDateTime.of(2026, 7, 30, 10, 0));
		jdbcTemplate.update("""
				INSERT INTO case_cameras
				(id, case_id, camera_id, search_enabled, selected_at, updated_at)
				VALUES (?, ?, ?, TRUE, ?, ?)
				""", 178005L, CASE_ID, CAMERA_ID,
				LocalDateTime.of(2026, 7, 30, 10, 0), LocalDateTime.of(2026, 7, 30, 10, 0));
		jdbcTemplate.update("""
				INSERT INTO search_conditions
				(id, case_id, prompt, similarity_threshold, created_at, updated_at)
				VALUES (?, ?, 'condition A', 0.7000, ?, ?),
				       (?, ?, 'condition B', 0.8000, ?, ?)
				""", 178006L, CASE_ID,
				LocalDateTime.of(2026, 7, 30, 10, 0), LocalDateTime.of(2026, 7, 30, 10, 0),
				178007L, CASE_ID,
				LocalDateTime.of(2026, 7, 30, 11, 0), LocalDateTime.of(2026, 7, 30, 11, 0));
	}

	@AfterEach
	void tearDown() {
		cleanup();
	}

	@Test
	void activeRowsKeepLatestTimestampFromDeletedCondition() {
		jdbcTemplate.update("""
				UPDATE search_conditions
				SET deleted_at = ?, updated_at = ?
				WHERE id = ?
				""", LocalDateTime.of(2026, 7, 30, 12, 0),
				LocalDateTime.of(2026, 7, 30, 12, 0), 178007L);

		List<DeviceSearchTargetRow> cameraRows = mapper.findDeviceSearchTargetCameras(MEDIA_SERVER_ID);
		List<DeviceSearchTargetRow> conditionRows = mapper.findDeviceSearchTargetConditions(List.of(CASE_ID));

		assertEquals(1, cameraRows.size());
		assertEquals(1, conditionRows.size());
		assertEquals(Instant.parse("2026-07-30T12:00:00Z"), cameraRows.getFirst().getUpdatedAt());
		assertNotNull(conditionRows.getFirst().getPrompt());
	}

	@Test
	void newConditionLeavesLegacyThresholdNullWithoutChangingExistingValues() {
		SearchConditionRow row = new SearchConditionRow();
		row.setCaseId(CASE_ID);
		row.setPrompt("a person wearing a blue long sleeve top and black pants");

		mapper.insertSearchCondition(row);

		assertNotNull(row.getId());
		assertNull(jdbcTemplate.queryForObject(
				"SELECT similarity_threshold FROM search_conditions WHERE id = ?",
				BigDecimal.class,
				row.getId()));
		assertEquals(new BigDecimal("0.7000"), jdbcTemplate.queryForObject(
				"SELECT similarity_threshold FROM search_conditions WHERE id = ?",
				BigDecimal.class,
				178006L));
	}

	@Test
	void lastModifiedIncludesLastSearchConditionDeletion() {
		jdbcTemplate.update("""
				UPDATE search_conditions
				SET deleted_at = ?, updated_at = ?
				WHERE case_id = ?
				""", LocalDateTime.of(2026, 7, 30, 12, 0),
				LocalDateTime.of(2026, 7, 30, 12, 0), CASE_ID);

		assertEquals(Instant.parse("2026-07-30T12:00:00Z"),
				mapper.findDeviceSearchTargetLastModified(MEDIA_SERVER_ID));
	}

	@Test
	void lastModifiedIncludesLastCameraDeactivation() {
		jdbcTemplate.update("""
				UPDATE case_cameras
				SET search_enabled = FALSE, removed_at = ?, updated_at = ?
				WHERE case_id = ? AND camera_id = ?
				""", LocalDateTime.of(2026, 7, 30, 13, 0),
				LocalDateTime.of(2026, 7, 30, 13, 0), CASE_ID, CAMERA_ID);

		assertEquals(Instant.parse("2026-07-30T13:00:00Z"),
				mapper.findDeviceSearchTargetLastModified(MEDIA_SERVER_ID));
	}

	@Test
	void lastModifiedIncludesCaseClosure() {
		jdbcTemplate.update("""
				UPDATE cases
				SET status = 'CLOSED', closed_at = ?, updated_at = ?
				WHERE id = ?
				""", LocalDateTime.of(2026, 7, 30, 14, 0),
				LocalDateTime.of(2026, 7, 30, 14, 0), CASE_ID);

		assertEquals(Instant.parse("2026-07-30T14:00:00Z"),
				mapper.findDeviceSearchTargetLastModified(MEDIA_SERVER_ID));
	}

	private void cleanup() {
		jdbcTemplate.update("DELETE FROM case_cameras WHERE case_id = ?", CASE_ID);
		jdbcTemplate.update("DELETE FROM search_conditions WHERE case_id = ?", CASE_ID);
		jdbcTemplate.update("DELETE FROM cases WHERE id = ?", CASE_ID);
		jdbcTemplate.update("DELETE FROM reporters WHERE id = ?", REPORTER_ID);
		jdbcTemplate.update("DELETE FROM cameras WHERE id = ?", CAMERA_ID);
		jdbcTemplate.update("DELETE FROM media_servers WHERE id = ?", MEDIA_SERVER_ID);
	}
}
