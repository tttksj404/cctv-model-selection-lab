package com.ssafy.eyesonu.recording.service;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertInstanceOf;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.when;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.auth.device.MediaServerPrincipal;
import com.ssafy.eyesonu.common.exception.ApiException;
import com.ssafy.eyesonu.recording.dto.device.RecordingCreateRequest;
import com.ssafy.eyesonu.storage.StorageObject;
import com.ssafy.eyesonu.storage.StorageObjectVerifier;
import java.time.OffsetDateTime;
import java.util.List;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.Future;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.transaction.support.TransactionSynchronizationManager;

@ActiveProfiles("test")
@SpringBootTest(properties = "spring.flyway.enabled=true")
@Import(TestDatabaseConfiguration.class)
class RecordingRegistrationConcurrencyTests {

    private static final long MEDIA_SERVER_ID = 162001L;
    private static final long CAMERA_A_ID = 163001L;
    private static final long CAMERA_B_ID = 163002L;
    private static final String CAMERA_A = "concurrency-camera-a";
    private static final String CAMERA_B = "concurrency-camera-b";
    private static final String KEY_1 = "550e8400-e29b-41d4-a716-446655440001";
    private static final String KEY_2 = "550e8400-e29b-41d4-a716-446655440002";

    @Autowired
    private RecordingCommandService service;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @MockitoBean
    private StorageObjectVerifier storageVerifier;

    private final MediaServerPrincipal principal = new MediaServerPrincipal(MEDIA_SERVER_ID, "concurrent");

    @BeforeEach
    void setUp() {
        cleanup();
        jdbcTemplate.update("""
                INSERT INTO media_servers
                    (id, server_code, name, device_key_id, device_key_hash, status)
                VALUES (?, 'recording-concurrency', 'Recording Concurrency',
                        'concurrent000001', 'fixture-hash', 'ACTIVE')
                """, MEDIA_SERVER_ID);
        insertCamera(CAMERA_A_ID, CAMERA_A);
        insertCamera(CAMERA_B_ID, CAMERA_B);
        when(storageVerifier.stat(anyString())).thenAnswer(invocation -> {
            assertFalse(TransactionSynchronizationManager.isActualTransactionActive());
            return new StorageObject(80L, "video/mp4");
        });
    }

    @AfterEach
    void tearDown() {
        cleanup();
    }

    @Test
    void sameKeyAndFingerprintCreateOnceAndReturnOneReplay() throws Exception {
        RecordingCreateRequest request = request(CAMERA_A, "same.mp4", 0);

        List<Object> outcomes = concurrently(
                () -> service.create(principal, CAMERA_A, KEY_1, request),
                () -> service.create(principal, CAMERA_A, KEY_1, request));

        assertEquals(1, outcomes.stream()
                .filter(RecordingCreateResult.class::isInstance)
                .map(RecordingCreateResult.class::cast)
                .filter(result -> !result.duplicate())
                .count());
        assertEquals(1, outcomes.stream()
                .filter(RecordingCreateResult.class::isInstance)
                .map(RecordingCreateResult.class::cast)
                .filter(RecordingCreateResult::duplicate)
                .count());
        assertDatabaseCounts(1, 1);
    }

    @Test
    void sameKeyAndDifferentFingerprintReturnConflictAndRollbackLoser() throws Exception {
        List<Object> outcomes = concurrently(
                () -> service.create(principal, CAMERA_A, KEY_1, request(CAMERA_A, "first.mp4", 0)),
                () -> service.create(principal, CAMERA_B, KEY_1, request(CAMERA_B, "second.mp4", 60)));

        assertEquals(1, outcomes.stream().filter(RecordingCreateResult.class::isInstance).count());
        ApiException conflict = singleApiException(outcomes);
        assertEquals(409, conflict.getStatus().value());
        assertEquals("IDEMPOTENCY_KEY_CONFLICT", conflict.getCode());
        assertDatabaseCounts(1, 1);
    }

    @Test
    void differentKeysAndSameObjectReturnDuplicateResourceAndRollbackLoser() throws Exception {
        RecordingCreateRequest request = request(CAMERA_A, "shared.mp4", 0);

        List<Object> outcomes = concurrently(
                () -> service.create(principal, CAMERA_A, KEY_1, request),
                () -> service.create(principal, CAMERA_A, KEY_2, request));

        assertEquals(1, outcomes.stream().filter(RecordingCreateResult.class::isInstance).count());
        ApiException conflict = singleApiException(outcomes);
        assertEquals(409, conflict.getStatus().value());
        assertEquals("DUPLICATE_RESOURCE", conflict.getCode());
        assertDatabaseCounts(1, 1);
    }

    private void insertCamera(long id, String code) {
        jdbcTemplate.update("""
                INSERT INTO cameras
                    (id, media_server_id, camera_name, camera_code, latitude, longitude,
                     address, stream_url, status)
                VALUES (?, ?, ?, ?, 37.5665000, 126.9780000, 'address', ?, 'OFFLINE')
                """, id, MEDIA_SERVER_ID, code, code, "rtsp://" + code + "/stream");
    }

    private RecordingCreateRequest request(String cameraCode, String fileName, long startOffsetSeconds) {
        OffsetDateTime start = OffsetDateTime.parse("2026-07-20T01:00:00Z")
                .plusSeconds(startOffsetSeconds);
        return new RecordingCreateRequest(
                start,
                start.plusMinutes(1),
                "recordings/" + cameraCode + "/" + fileName);
    }

    private List<Object> concurrently(Callable<?> first, Callable<?> second) throws Exception {
        CountDownLatch ready = new CountDownLatch(2);
        CountDownLatch start = new CountDownLatch(1);
        try (ExecutorService executor = Executors.newFixedThreadPool(2)) {
            Future<Object> firstFuture = executor.submit(awaitStart(ready, start, first));
            Future<Object> secondFuture = executor.submit(awaitStart(ready, start, second));
            if (!ready.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("Concurrent requests did not become ready");
            }
            start.countDown();
            return List.of(outcome(firstFuture), outcome(secondFuture));
        }
    }

    private Callable<Object> awaitStart(
            CountDownLatch ready, CountDownLatch start, Callable<?> action) {
        return () -> {
            ready.countDown();
            if (!start.await(5, TimeUnit.SECONDS)) {
                throw new AssertionError("Concurrent start was not released");
            }
            return action.call();
        };
    }

    private Object outcome(Future<Object> future) throws Exception {
        try {
            return future.get(15, TimeUnit.SECONDS);
        } catch (ExecutionException exception) {
            return exception.getCause();
        }
    }

    private ApiException singleApiException(List<Object> outcomes) {
        List<Object> exceptions = outcomes.stream()
                .filter(ApiException.class::isInstance)
                .toList();
        assertEquals(1, exceptions.size(), () -> "Unexpected outcomes: " + outcomes);
        return assertInstanceOf(ApiException.class, exceptions.getFirst());
    }

    private void assertDatabaseCounts(int recordings, int registrations) {
        assertEquals(recordings, jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM recordings
                WHERE camera_id IN (?, ?)
                """, Integer.class, CAMERA_A_ID, CAMERA_B_ID));
        assertEquals(registrations, jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM recording_registration_requests
                WHERE media_server_id = ?
                """, Integer.class, MEDIA_SERVER_ID));
    }

    private void cleanup() {
        jdbcTemplate.update(
                "DELETE FROM recording_registration_requests WHERE media_server_id = ?",
                MEDIA_SERVER_ID);
        jdbcTemplate.update(
                "DELETE FROM recordings WHERE camera_id IN (?, ?)",
                CAMERA_A_ID,
                CAMERA_B_ID);
        jdbcTemplate.update(
                "DELETE FROM cameras WHERE id IN (?, ?)",
                CAMERA_A_ID,
                CAMERA_B_ID);
        jdbcTemplate.update("DELETE FROM media_servers WHERE id = ?", MEDIA_SERVER_ID);
    }
}
