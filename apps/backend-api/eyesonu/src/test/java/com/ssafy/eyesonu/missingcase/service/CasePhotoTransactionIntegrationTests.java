package com.ssafy.eyesonu.missingcase.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.storage.StorageObjectUrlSigner;
import com.ssafy.eyesonu.storage.StorageObjectWriter;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.ConcurrentLinkedQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataAccessException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ActiveProfiles("test")
@SpringBootTest(properties = "spring.flyway.enabled=true")
@Import(TestDatabaseConfiguration.class)
class CasePhotoTransactionIntegrationTests {

	private static final long ADMIN_ID = 172001L;
	private static final long REPORTER_ID = 172002L;
	private static final long CASE_ID = 172003L;
	private static final String OLD_KEY = "cases/172003/photos/old.jpg";

	@Autowired
	private CasePhotoService service;

	@Autowired
	private JdbcTemplate jdbcTemplate;

	@MockitoBean
	private StorageObjectWriter objectWriter;

	@MockitoBean
	private StorageObjectUrlSigner urlSigner;

	private final ConcurrentLinkedQueue<String> uploadedKeys = new ConcurrentLinkedQueue<>();
	private final ConcurrentLinkedQueue<String> deletedKeys = new ConcurrentLinkedQueue<>();

	@BeforeEach
	void setUp() {
		cleanup();
		jdbcTemplate.update("""
				INSERT INTO admins (id, login_id, password_hash, name)
				VALUES (?, 'case-photo-transaction', 'test-password-hash', 'Photo Admin')
				""", ADMIN_ID);
		jdbcTemplate.update("""
				INSERT INTO reporters (id, name, phone)
				VALUES (?, 'Photo Reporter', '01017201720')
				""", REPORTER_ID);
		jdbcTemplate.update("""
				INSERT INTO cases
				(id, reporter_id, case_number, status, report_content, missing_name, gender,
				 distinctive_features, photo_s3_key, last_seen_time, last_seen_address)
				VALUES (?, ?, 'EFU-PHOTO-172003', 'SEARCHING', 'content', 'Missing', 'UNKNOWN',
				        'blue coat', ?, UTC_TIMESTAMP(6), 'address')
				""", CASE_ID, REPORTER_ID, OLD_KEY);

		doAnswer(invocation -> {
			assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
			uploadedKeys.add(invocation.getArgument(0, String.class));
			return null;
		}).when(objectWriter).put(anyString(), any(byte[].class), anyString());
		doAnswer(invocation -> {
			assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
			deletedKeys.add(invocation.getArgument(0, String.class));
			return null;
		}).when(objectWriter).delete(anyString());
		when(urlSigner.createGetUrl(anyString())).thenAnswer(invocation -> {
			assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
			return "https://storage.example/" + invocation.getArgument(0, String.class);
		});
	}

	@AfterEach
	void tearDown() {
		cleanup();
		uploadedKeys.clear();
		deletedKeys.clear();
	}

	@Test
	void storageCallsRunOutsideTransactionAndMetadataAuditCommitTogether() {
		String photoUrl = service.put(CASE_ID, jpeg("boundary.jpg"), ADMIN_ID).photoUrl();
		String storedKey = photoKey();

		assertTrue(photoUrl.endsWith(storedKey));
		assertEquals(List.of(storedKey), new ArrayList<>(uploadedKeys));
		assertEquals(List.of(OLD_KEY), new ArrayList<>(deletedKeys));
		assertEquals(1, jdbcTemplate.queryForObject("""
				SELECT COUNT(*) FROM audit_logs
				WHERE case_id = ? AND action_type = 'CASE_PHOTO_REPLACED'
				""", Integer.class, CASE_ID));
	}

	@Test
	void auditFailureRollsBackMetadataAndCompensatesNewObject() {
		assertThrows(
				DataAccessException.class,
				() -> service.put(CASE_ID, jpeg("rollback.jpg"), Long.MAX_VALUE));

		assertEquals(OLD_KEY, photoKey());
		assertEquals(1, uploadedKeys.size());
		assertEquals(new ArrayList<>(uploadedKeys), new ArrayList<>(deletedKeys));
	}

	@Test
	void closingCaseDuringUploadRejectsFinalWriteAndCompensatesObject() throws Exception {
		CountDownLatch uploadStarted = new CountDownLatch(1);
		CountDownLatch resumeUpload = new CountDownLatch(1);
		doAnswer(invocation -> {
			assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
			uploadedKeys.add(invocation.getArgument(0, String.class));
			uploadStarted.countDown();
			if (!resumeUpload.await(5, TimeUnit.SECONDS)) {
				throw new AssertionError("Photo upload was not resumed");
			}
			return null;
		}).when(objectWriter).put(anyString(), any(byte[].class), anyString());

		try (ExecutorService executor = Executors.newSingleThreadExecutor()) {
			Future<?> upload = executor.submit(() -> service.put(CASE_ID, jpeg("closing.jpg"), ADMIN_ID));
			assertTrue(uploadStarted.await(5, TimeUnit.SECONDS));
			jdbcTemplate.update("""
					UPDATE cases
					SET status = 'CLOSED', closed_at = UTC_TIMESTAMP(6)
					WHERE id = ?
					""", CASE_ID);
			resumeUpload.countDown();

			ExecutionException failure = assertThrows(
					ExecutionException.class, () -> upload.get(15, TimeUnit.SECONDS));
			ApiException exception = assertInstanceOf(ApiException.class, failure.getCause());
			assertEquals("BUSINESS_RULE_VIOLATION", exception.getCode());
		}
		finally {
			resumeUpload.countDown();
		}

		assertEquals(OLD_KEY, photoKey());
		assertEquals(new ArrayList<>(uploadedKeys), new ArrayList<>(deletedKeys));
	}

	@Test
	void concurrentReplacementsKeepFinalObjectAndDeleteOldAndLosingObjects() throws Exception {
		runConcurrently(
				() -> service.put(CASE_ID, jpeg("first.jpg"), ADMIN_ID),
				() -> service.put(CASE_ID, jpeg("second.jpg"), ADMIN_ID));

		String storedKey = photoKey();
		assertEquals(2, uploadedKeys.size());
		assertTrue(uploadedKeys.contains(storedKey));
		assertTrue(deletedKeys.contains(OLD_KEY));
		assertTrue(uploadedKeys.stream()
				.filter(key -> !key.equals(storedKey))
				.allMatch(deletedKeys::contains));
		assertFalse(deletedKeys.contains(storedKey));
	}

	@Test
	void concurrentReplacementAndRemovalFollowLastCommittedMetadataChange() throws Exception {
		runConcurrently(
				() -> service.put(CASE_ID, jpeg("replacement.jpg"), ADMIN_ID),
				() -> {
					service.delete(CASE_ID, ADMIN_ID);
					return "deleted";
				});

		String uploadedKey = uploadedKeys.element();
		String storedKey = photoKey();
		assertTrue(deletedKeys.contains(OLD_KEY));
		if (storedKey == null) {
			assertTrue(deletedKeys.contains(uploadedKey));
		}
		else {
			assertEquals(uploadedKey, storedKey);
			assertFalse(deletedKeys.contains(uploadedKey));
		}
	}

	private void runConcurrently(Callable<?> first, Callable<?> second) throws Exception {
		CountDownLatch ready = new CountDownLatch(2);
		CountDownLatch start = new CountDownLatch(1);
		try (ExecutorService executor = Executors.newFixedThreadPool(2)) {
			Future<?> firstFuture = executor.submit(awaitStart(ready, start, first));
			Future<?> secondFuture = executor.submit(awaitStart(ready, start, second));
			if (!ready.await(5, TimeUnit.SECONDS)) {
				throw new AssertionError("Concurrent photo requests did not become ready");
			}
			start.countDown();
			firstFuture.get(15, TimeUnit.SECONDS);
			secondFuture.get(15, TimeUnit.SECONDS);
		}
	}

	private Callable<Object> awaitStart(
			CountDownLatch ready, CountDownLatch start, Callable<?> action) {
		return () -> {
			ready.countDown();
			if (!start.await(5, TimeUnit.SECONDS)) {
				throw new AssertionError("Concurrent photo start was not released");
			}
			return action.call();
		};
	}

	private MockMultipartFile jpeg(String name) {
		return new MockMultipartFile(
				"photo", name, "image/jpeg",
				new byte[] {(byte) 0xff, (byte) 0xd8, (byte) 0xff, 0x01});
	}

	private String photoKey() {
		return jdbcTemplate.queryForObject(
				"SELECT photo_s3_key FROM cases WHERE id = ?", String.class, CASE_ID);
	}

	private void cleanup() {
		jdbcTemplate.update("DELETE FROM audit_logs WHERE case_id = ? OR admin_id = ?", CASE_ID, ADMIN_ID);
		jdbcTemplate.update("DELETE FROM cases WHERE id = ?", CASE_ID);
		jdbcTemplate.update("DELETE FROM reporters WHERE id = ?", REPORTER_ID);
		jdbcTemplate.update("DELETE FROM admins WHERE id = ?", ADMIN_ID);
	}
}
