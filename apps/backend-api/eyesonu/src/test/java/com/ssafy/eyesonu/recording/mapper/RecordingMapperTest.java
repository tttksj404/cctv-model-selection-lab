package com.ssafy.eyesonu.recording.mapper;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNull;
import static org.junit.jupiter.api.Assertions.assertThrows;

import com.ssafy.eyesonu.TestDatabaseConfiguration;
import com.ssafy.eyesonu.camera.domain.Camera;
import com.ssafy.eyesonu.camera.mapper.CameraMapper;
import com.ssafy.eyesonu.recording.domain.AdminRecordingRow;
import com.ssafy.eyesonu.recording.domain.Recording;
import com.ssafy.eyesonu.recording.domain.RecordingRegistration;
import com.ssafy.eyesonu.recording.domain.RecordingRegistrationResult;
import com.ssafy.eyesonu.recording.domain.RecordingSortDirection;
import com.ssafy.eyesonu.recording.domain.RecordingSortField;
import java.sql.Timestamp;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.context.annotation.Import;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;
import org.springframework.test.context.jdbc.Sql;
import org.springframework.test.context.jdbc.Sql.ExecutionPhase;
import org.springframework.test.context.jdbc.SqlConfig;
import org.springframework.transaction.annotation.Transactional;

@SpringBootTest(properties = "spring.flyway.enabled=true")
@ActiveProfiles("test")
@Import(TestDatabaseConfiguration.class)
@Transactional
@Sql(
        scripts = "/recording-fixture.sql",
        executionPhase = ExecutionPhase.BEFORE_TEST_METHOD,
        config = @SqlConfig(transactionMode = SqlConfig.TransactionMode.INFERRED))
class RecordingMapperTest {

    private static final Long MEDIA_SERVER_ID = 152001L;
    private static final Long OTHER_MEDIA_SERVER_ID = 152002L;
    private static final Long CAMERA_ID = 153001L;
    private static final Long OTHER_CAMERA_ID = 153002L;
    private static final String CAMERA_CODE = "recording-fixture-camera-153001";
    private static final Instant BASE_TIME = Instant.parse("2026-07-23T09:00:00.123456Z");

    @Autowired
    private RecordingMapper recordingMapper;

    @Autowired
    private CameraMapper cameraMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void v3RemovesUploadStatusAndCreatesRegistrationTable() {
        Integer uploadStatusColumns = jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM information_schema.columns
                WHERE table_schema = DATABASE()
                  AND table_name = 'recordings'
                  AND column_name = 'upload_status'
                """, Integer.class);
        Integer registrationTables = jdbcTemplate.queryForObject("""
                SELECT COUNT(*)
                FROM information_schema.tables
                WHERE table_schema = DATABASE()
                  AND table_name = 'recording_registration_requests'
                """, Integer.class);

        assertThat(uploadStatusColumns).isZero();
        assertThat(registrationTables).isOne();
    }

    @Test
    void v3IndexesMatchFiltersAndStablePageSorts() {
        Map<String, String> indexes = jdbcTemplate.query("""
                SELECT index_name,
                       GROUP_CONCAT(
                           CONCAT(column_name, ':', collation)
                           ORDER BY seq_in_index SEPARATOR ',') AS columns_and_order
                FROM information_schema.statistics
                WHERE table_schema = DATABASE()
                  AND table_name = 'recordings'
                  AND index_name LIKE 'ix_recordings_%'
                GROUP BY index_name
                """, resultSet -> {
            java.util.LinkedHashMap<String, String> result = new java.util.LinkedHashMap<>();
            while (resultSet.next()) {
                result.put(resultSet.getString("index_name"), resultSet.getString("columns_and_order"));
            }
            return result;
        });

        assertThat(indexes).containsEntry(
                "ix_recordings_camera_start_id", "camera_id:A,start_time:D,id:D");
        assertThat(indexes).containsEntry(
                "ix_recordings_start_id", "start_time:D,id:D");
        assertThat(indexes).containsEntry(
                "ix_recordings_camera_end_id", "camera_id:A,end_time:A,id:D");
        assertThat(indexes).containsEntry(
                "ix_recordings_end_id", "end_time:A,id:D");
        assertThat(indexes).containsEntry(
                "ix_recordings_camera_created_id", "camera_id:A,created_at:D,id:D");
        assertThat(indexes).containsEntry(
                "ix_recordings_created_id", "created_at:D,id:D");
    }

    @Test
    void cameraLookupReturnsOwnershipAndSummaryAndSupportsLockingLookup() {
        Camera camera = cameraMapper.findByCameraCode(CAMERA_CODE).orElseThrow();
        Camera locked = cameraMapper.findByCameraCodeForUpdate(CAMERA_CODE).orElseThrow();

        assertThat(camera).isEqualTo(new Camera(
                CAMERA_ID,
                MEDIA_SERVER_ID,
                CAMERA_CODE,
                "Recording Mapper Fixture Camera 1"));
        assertThat(locked).isEqualTo(camera);
    }

    @Test
    void insertAndReselectPreserveUtcMicrosecondsAndDatabaseCreatedAt() {
        Recording recording = recording(CAMERA_ID, "instant-round-trip", BASE_TIME, 100L);

        assertEquals(1, recordingMapper.insert(recording));
        assertThat(recording.getId()).isPositive();

        Recording found = recordingMapper.findById(recording.getId());
        assertThat(found.getStartTime()).isEqualTo(BASE_TIME);
        assertThat(found.getEndTime()).isEqualTo(BASE_TIME.plus(1, ChronoUnit.MINUTES));
        assertThat(found.getCreatedAt()).isNotNull();
        assertThat(found.getCreatedAt().getNano() % 1_000).isZero();
    }

    @Test
    void s3KeyUniqueConstraintIsCaseSensitive() {
        Recording upperCase = insert(CAMERA_ID, "CaseSensitive", BASE_TIME);
        Recording lowerCase = insert(CAMERA_ID, "casesensitive", BASE_TIME.plusSeconds(60));

        assertThat(recordingMapper.findByS3Key(upperCase.getS3Key()).getId()).isEqualTo(upperCase.getId());
        assertThat(recordingMapper.findByS3Key(lowerCase.getS3Key()).getId()).isEqualTo(lowerCase.getId());
        assertThat(upperCase.getId()).isNotEqualTo(lowerCase.getId());
    }

    @Test
    void duplicateS3KeyViolatesUniqueConstraint() {
        Recording inserted = insert(CAMERA_ID, "duplicate", BASE_TIME);

        assertThrows(DataIntegrityViolationException.class,
                () -> recordingMapper.insert(recording(
                        CAMERA_ID, inserted.getS3Key(), BASE_TIME.plusSeconds(60), 100L)));
    }

    @Test
    void fileSizeMustBePresentAndPositive() {
        assertThrows(DataAccessException.class,
                () -> recordingMapper.insert(recording(CAMERA_ID, "null-size", BASE_TIME, null)));
        assertThrows(DataAccessException.class,
                () -> recordingMapper.insert(recording(CAMERA_ID, "zero-size", BASE_TIME, 0L)));
        assertThrows(DataAccessException.class,
                () -> recordingMapper.insert(recording(CAMERA_ID, "negative-size", BASE_TIME, -1L)));
    }

    @Test
    void endTimeMustBeStrictlyAfterStartTime() {
        Recording equal = recording(CAMERA_ID, "equal-time", BASE_TIME, 100L);
        equal.setEndTime(BASE_TIME);
        Recording reversed = recording(CAMERA_ID, "reversed-time", BASE_TIME, 100L);
        reversed.setEndTime(BASE_TIME.minusSeconds(1));

        assertThrows(DataAccessException.class, () -> recordingMapper.insert(equal));
        assertThrows(DataAccessException.class, () -> recordingMapper.insert(reversed));
    }

    @Test
    void registrationLookupReturnsFingerprintAndJoinedRecording() {
        Recording recording = insert(CAMERA_ID, "registration-lookup", BASE_TIME);
        RecordingRegistration registration = registration(
                MEDIA_SERVER_ID,
                "00000000-0000-0000-0000-000000000001",
                "a".repeat(64),
                recording.getId());

        assertEquals(1, recordingMapper.insertRegistration(registration));

        RecordingRegistrationResult found = recordingMapper.findRegistrationByKey(
                MEDIA_SERVER_ID, registration.getIdempotencyKey());
        assertThat(found.getRequestFingerprint()).isEqualTo(registration.getRequestFingerprint());
        assertThat(found.getRecording().getId()).isEqualTo(recording.getId());
        assertThat(found.getRecording().getCreatedAt()).isNotNull();
        assertThat(found.getRecording().getStartTime()).isEqualTo(BASE_TIME);
    }

    @Test
    void idempotencyKeyIsScopedByMediaServer() {
        String sharedKey = "00000000-0000-0000-0000-000000000002";
        Recording first = insert(CAMERA_ID, "scoped-first", BASE_TIME);
        Recording second = insert(OTHER_CAMERA_ID, "scoped-second", BASE_TIME);

        assertEquals(1, recordingMapper.insertRegistration(
                registration(MEDIA_SERVER_ID, sharedKey, "b".repeat(64), first.getId())));
        assertEquals(1, recordingMapper.insertRegistration(
                registration(OTHER_MEDIA_SERVER_ID, sharedKey, "c".repeat(64), second.getId())));

        assertThat(recordingMapper.findRegistrationByKey(MEDIA_SERVER_ID, sharedKey)
                .getRecording().getId()).isEqualTo(first.getId());
        assertThat(recordingMapper.findRegistrationByKey(OTHER_MEDIA_SERVER_ID, sharedKey)
                .getRecording().getId()).isEqualTo(second.getId());
    }

    @Test
    void registrationRejectsDuplicateScopeAndRecordingReuse() {
        Recording first = insert(CAMERA_ID, "registration-unique-first", BASE_TIME);
        Recording second = insert(CAMERA_ID, "registration-unique-second", BASE_TIME.plusSeconds(60));
        String key = "00000000-0000-0000-0000-000000000003";
        recordingMapper.insertRegistration(registration(MEDIA_SERVER_ID, key, "d".repeat(64), first.getId()));

        assertThrows(DataIntegrityViolationException.class,
                () -> recordingMapper.insertRegistration(registration(
                        MEDIA_SERVER_ID, key, "e".repeat(64), second.getId())));
        assertThrows(DataIntegrityViolationException.class,
                () -> recordingMapper.insertRegistration(registration(
                        OTHER_MEDIA_SERVER_ID,
                        "00000000-0000-0000-0000-000000000004",
                        "f".repeat(64),
                        first.getId())));
    }

    @Test
    void adminPeriodFilterUsesHalfOpenIntervalOverlap() {
        Instant from = BASE_TIME.plusSeconds(60);
        Instant to = BASE_TIME.plusSeconds(180);
        insertInterval("ends-at-from", BASE_TIME, from);
        Recording overlapsStart = insertInterval(
                "overlaps-start", from.minusSeconds(1), from.plusSeconds(1));
        Recording inside = insertInterval("inside", from, to);
        Recording overlapsEnd = insertInterval(
                "overlaps-end", to.minusSeconds(1), to.plusSeconds(1));
        insertInterval("starts-at-to", to, to.plusSeconds(60));

        List<AdminRecordingRow> rows = recordingMapper.findAdminPage(
                null,
                from,
                to,
                RecordingSortField.START_TIME,
                RecordingSortDirection.ASC,
                20,
                0);

        assertThat(rows).extracting(AdminRecordingRow::getId)
                .containsExactly(overlapsStart.getId(), inside.getId(), overlapsEnd.getId());
        assertThat(recordingMapper.countAdminRecordings(null, from, to)).isEqualTo(3);
    }

    @Test
    void adminFiltersAcceptEitherOpenBoundaryAndCameraId() {
        insertInterval("camera-one-old", BASE_TIME, BASE_TIME.plusSeconds(60));
        Recording cameraOneNew = insertInterval(
                "camera-one-new", BASE_TIME.plusSeconds(120), BASE_TIME.plusSeconds(180));
        insertIntervalForCamera(
                OTHER_CAMERA_ID,
                "camera-two-new",
                BASE_TIME.plusSeconds(120),
                BASE_TIME.plusSeconds(180));

        assertThat(recordingMapper.countAdminRecordings(
                CAMERA_ID, BASE_TIME.plusSeconds(60), null)).isEqualTo(1);
        assertThat(recordingMapper.countAdminRecordings(
                CAMERA_ID, null, BASE_TIME.plusSeconds(120))).isEqualTo(1);
        assertThat(recordingMapper.findAdminPage(
                        CAMERA_ID,
                        BASE_TIME.plusSeconds(60),
                        null,
                        RecordingSortField.START_TIME,
                        RecordingSortDirection.DESC,
                        20,
                        0))
                .extracting(AdminRecordingRow::getId)
                .containsExactly(cameraOneNew.getId());
    }

    @Test
    void adminPageAppliesLimitOffsetSortAndDescendingIdTieBreaker() {
        Recording old = insert(CAMERA_ID, "page-old", BASE_TIME);
        Recording tieFirst = insert(CAMERA_ID, "page-tie-first", BASE_TIME.plusSeconds(60));
        Recording tieSecond = insert(CAMERA_ID, "page-tie-second", BASE_TIME.plusSeconds(60));
        Recording newest = insert(CAMERA_ID, "page-newest", BASE_TIME.plusSeconds(120));

        List<AdminRecordingRow> firstPage = recordingMapper.findAdminPage(
                null, null, null,
                RecordingSortField.START_TIME, RecordingSortDirection.ASC,
                2, 0);
        List<AdminRecordingRow> secondPage = recordingMapper.findAdminPage(
                null, null, null,
                RecordingSortField.START_TIME, RecordingSortDirection.ASC,
                2, 2);

        assertThat(firstPage).extracting(AdminRecordingRow::getId)
                .containsExactly(old.getId(), tieSecond.getId());
        assertThat(secondPage).extracting(AdminRecordingRow::getId)
                .containsExactly(tieFirst.getId(), newest.getId());
    }

    @Test
    void adminPageSupportsCreatedAtSortWithoutDynamicSqlInput() {
        Recording later = insert(CAMERA_ID, "created-later", BASE_TIME);
        Recording earlier = insert(CAMERA_ID, "created-earlier", BASE_TIME.plusSeconds(60));
        jdbcTemplate.update(
                "UPDATE recordings SET created_at = ? WHERE id = ?",
                Timestamp.from(BASE_TIME.plusSeconds(10)),
                later.getId());
        jdbcTemplate.update(
                "UPDATE recordings SET created_at = ? WHERE id = ?",
                Timestamp.from(BASE_TIME),
                earlier.getId());

        List<AdminRecordingRow> rows = recordingMapper.findAdminPage(
                null, null, null,
                RecordingSortField.CREATED_AT, RecordingSortDirection.ASC,
                20, 0);

        assertThat(rows).extracting(AdminRecordingRow::getId)
                .containsExactly(earlier.getId(), later.getId());
    }

    @Test
    void adminDetailIncludesCameraSummaryAndInternalStorageKey() {
        Recording recording = insert(CAMERA_ID, "admin-detail", BASE_TIME);

        AdminRecordingRow row = recordingMapper.findAdminDetail(recording.getId());

        assertThat(row.getCameraId()).isEqualTo(CAMERA_ID);
        assertThat(row.getCameraCode()).isEqualTo(CAMERA_CODE);
        assertThat(row.getCameraName()).isEqualTo("Recording Mapper Fixture Camera 1");
        assertThat(row.getS3Key()).isEqualTo(recording.getS3Key());
        assertThat(recordingMapper.findAdminDetail(Long.MAX_VALUE)).isNull();
        assertNull(recordingMapper.findById(Long.MAX_VALUE));
    }

    private Recording insert(Long cameraId, String suffix, Instant startTime) {
        Recording recording = recording(cameraId, storageKey(cameraId, suffix), startTime, 100L);
        assertEquals(1, recordingMapper.insert(recording));
        return recording;
    }

    private Recording insertInterval(String suffix, Instant startTime, Instant endTime) {
        return insertIntervalForCamera(CAMERA_ID, suffix, startTime, endTime);
    }

    private Recording insertIntervalForCamera(
            Long cameraId, String suffix, Instant startTime, Instant endTime) {
        Recording recording = recording(cameraId, storageKey(cameraId, suffix), startTime, 100L);
        recording.setEndTime(endTime);
        assertEquals(1, recordingMapper.insert(recording));
        return recording;
    }

    private Recording recording(Long cameraId, String s3Key, Instant startTime, Long fileSize) {
        return new Recording(
                null,
                cameraId,
                startTime,
                startTime.plus(1, ChronoUnit.MINUTES),
                s3Key,
                fileSize,
                null);
    }

    private RecordingRegistration registration(
            Long mediaServerId, String key, String fingerprint, Long recordingId) {
        return new RecordingRegistration(mediaServerId, key, fingerprint, recordingId, null);
    }

    private String storageKey(Long cameraId, String suffix) {
        return "recordings/camera-" + cameraId + "/" + suffix + ".mp4";
    }
}
