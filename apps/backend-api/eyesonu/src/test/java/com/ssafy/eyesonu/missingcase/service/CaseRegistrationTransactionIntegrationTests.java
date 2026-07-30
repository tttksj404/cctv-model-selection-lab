package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.missingcase.domain.CaseStatus;
import com.ssafy.eyesonu.missingcase.domain.Gender;
import com.ssafy.eyesonu.missingcase.domain.MissingCaseRow;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateRequest;
import com.ssafy.eyesonu.missingcase.dto.admin.CaseCreateResponse;
import java.time.Instant;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.PlatformTransactionManager;
import org.springframework.transaction.support.TransactionTemplate;

@ActiveProfiles("test")
@SpringBootTest(properties = "spring.flyway.enabled=true")
@Import(TestDatabaseConfiguration.class)
class CaseRegistrationTransactionIntegrationTests {

	private static final long ADMIN_ID = 173001L;
	private static final long EXISTING_REPORTER_ID = 173002L;
	private static final long EXISTING_CASE_ID = 173003L;
	private static final String COLLIDING_NUMBER = "EFU-00000000000000000000000000";
	private static final String RETRIED_NUMBER = "EFU-11111111111111111111111111";
	private static final String OUTER_ROLLBACK_NUMBER = "EFU-22222222222222222222222222";
	private static final String AUDIT_FAILURE_NUMBER = "EFU-33333333333333333333333333";
	private static final String EXISTING_PHONE = "01017300000";
	private static final String RETRIED_PHONE = "01017300001";
	private static final String OUTER_ROLLBACK_PHONE = "01017300002";
	private static final String AUDIT_FAILURE_PHONE = "01017300003";

	@Autowired
	private CaseCommandService commandService;

	@Autowired
	private CaseRegistrationWriter registrationWriter;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@Autowired
	private PlatformTransactionManager transactionManager;

	@MockitoBean
	private CaseRequestValidator validator;

	@MockitoBean
	private CaseNumberGenerator caseNumberGenerator;

	@BeforeEach
	void setUp() {
		cleanup();
		jdbcTemplate.update("""
				INSERT INTO admins (id, login_id, password_hash, name)
				VALUES (?, 'case-registration-transaction', 'test-password-hash', 'Registration Admin')
				""", ADMIN_ID);
		jdbcTemplate.update("""
				INSERT INTO reporters (id, name, phone)
				VALUES (?, 'Existing Reporter', ?)
				""", EXISTING_REPORTER_ID, EXISTING_PHONE);
		jdbcTemplate.update("""
				INSERT INTO cases
				(id, reporter_id, case_number, status, report_content, missing_name, gender,
				 distinctive_features, last_seen_time, last_seen_address)
				VALUES (?, ?, ?, 'RECEIVED', 'existing content', 'Existing Missing', 'UNKNOWN',
				        'existing feature', UTC_TIMESTAMP(6), 'existing address')
				""", EXISTING_CASE_ID, EXISTING_REPORTER_ID, COLLIDING_NUMBER);
	}

	@AfterEach
	void tearDown() {
		cleanup();
	}

	@Test
	void collisionRetryDoesNotMarkOuterTransactionRollbackOnly() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		when(validator.normalizeCreate(request)).thenReturn(row(RETRIED_PHONE));
		when(caseNumberGenerator.generate()).thenReturn(COLLIDING_NUMBER, RETRIED_NUMBER);
		TransactionTemplate outer = new TransactionTemplate(transactionManager);

		CaseCreateResponse created = outer.execute(status -> {
			CaseCreateResponse response = commandService.create(request, ADMIN_ID);
			assertFalse(status.isRollbackOnly());
			jdbcTemplate.update(
					"UPDATE admins SET name = 'Outer Transaction Committed' WHERE id = ?", ADMIN_ID);
			return response;
		});

		assertNotNull(created);
		assertEquals(RETRIED_NUMBER, created.caseNumber());
		assertEquals("Outer Transaction Committed", jdbcTemplate.queryForObject(
				"SELECT name FROM admins WHERE id = ?", String.class, ADMIN_ID));
		assertEquals(1, count("SELECT COUNT(*) FROM reporters WHERE phone = ?", RETRIED_PHONE));
		assertEquals(1, count("SELECT COUNT(*) FROM cases WHERE case_number = ?", RETRIED_NUMBER));
		assertEquals(1, count("""
				SELECT COUNT(*) FROM audit_logs
				WHERE case_id = ? AND action_type = 'CASE_CREATED'
				""", created.id()));
	}

	@Test
	void successfulRegistrationRemainsCommittedAfterOuterRollback() {
		CaseCreateRequest request = mock(CaseCreateRequest.class);
		when(validator.normalizeCreate(request)).thenReturn(row(OUTER_ROLLBACK_PHONE));
		when(caseNumberGenerator.generate()).thenReturn(OUTER_ROLLBACK_NUMBER);
		TransactionTemplate outer = new TransactionTemplate(transactionManager);

		outer.executeWithoutResult(status -> {
			commandService.create(request, ADMIN_ID);
			status.setRollbackOnly();
		});

		assertEquals(1, count(
				"SELECT COUNT(*) FROM reporters WHERE phone = ?", OUTER_ROLLBACK_PHONE));
		assertEquals(1, count(
				"SELECT COUNT(*) FROM cases WHERE case_number = ?", OUTER_ROLLBACK_NUMBER));
		assertEquals(1, count("""
				SELECT COUNT(*) FROM audit_logs a
				INNER JOIN cases c ON c.id = a.case_id
				WHERE c.case_number = ? AND a.action_type = 'CASE_CREATED'
				""", OUTER_ROLLBACK_NUMBER));
	}

	@Test
	void auditFailureRollsBackReporterAndCase() {
		MissingCaseRow row = row(AUDIT_FAILURE_PHONE);
		row.setCaseNumber(AUDIT_FAILURE_NUMBER);

		assertThrows(DataAccessException.class, () -> registrationWriter.write(row, Long.MAX_VALUE));

		assertEquals(0, count(
				"SELECT COUNT(*) FROM reporters WHERE phone = ?", AUDIT_FAILURE_PHONE));
		assertEquals(0, count(
				"SELECT COUNT(*) FROM cases WHERE case_number = ?", AUDIT_FAILURE_NUMBER));
	}

	private MissingCaseRow row(String reporterPhone) {
		MissingCaseRow row = new MissingCaseRow();
		row.setReporterName("Registration Reporter");
		row.setReporterPhone(reporterPhone);
		row.setReporterRelation("Guardian");
		row.setStatus(CaseStatus.RECEIVED);
		row.setReportContent("registration content");
		row.setMissingName("Registration Missing");
		row.setGender(Gender.UNKNOWN);
		row.setDistinctiveFeatures("registration feature");
		row.setLastSeenTime(Instant.parse("2026-07-30T00:00:00Z"));
		row.setLastSeenAddress("registration address");
		return row;
	}

	private int count(String sql, Object... arguments) {
		return jdbcTemplate.queryForObject(sql, Integer.class, arguments);
	}

	private void cleanup() {
		jdbcTemplate.update("""
				DELETE FROM audit_logs
				WHERE admin_id = ? OR case_id IN (
				    SELECT id FROM cases WHERE case_number IN (?, ?, ?, ?)
				)
				""", ADMIN_ID, COLLIDING_NUMBER, RETRIED_NUMBER,
				OUTER_ROLLBACK_NUMBER, AUDIT_FAILURE_NUMBER);
		jdbcTemplate.update(
				"DELETE FROM cases WHERE case_number IN (?, ?, ?, ?)",
				COLLIDING_NUMBER, RETRIED_NUMBER, OUTER_ROLLBACK_NUMBER, AUDIT_FAILURE_NUMBER);
		jdbcTemplate.update(
				"DELETE FROM reporters WHERE phone IN (?, ?, ?, ?)",
				EXISTING_PHONE, RETRIED_PHONE, OUTER_ROLLBACK_PHONE, AUDIT_FAILURE_PHONE);
		jdbcTemplate.update("DELETE FROM admins WHERE id = ?", ADMIN_ID);
	}
}
